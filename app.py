from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
from datetime import datetime, timedelta
import json

app = Flask(__name__)
DB_PATH = 'appointments.db'
APPOINTMENT_DURATION_MINUTES = 20

# ─────────────────────────────────────────────
#  Database Setup
# ─────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS doctors (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialty TEXT NOT NULL,
            available_slots TEXT NOT NULL   -- JSON array of time strings
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name     TEXT NOT NULL,
            patient_email    TEXT,
            patient_phone    TEXT,
            doctor_id        INTEGER NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            reason           TEXT,
            status           TEXT DEFAULT 'Confirmed',
            created_at       TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (doctor_id) REFERENCES doctors(id)
        )
    ''')

    # Seed doctors if table is empty
    count = cur.execute("SELECT COUNT(*) FROM doctors").fetchone()[0]
    if count == 0:
        doctors = [
            ("Dr. Arjun Mehta",  "Cardiology",       json.dumps(["09:00 AM","10:00 AM","11:00 AM","02:00 PM","03:00 PM","04:00 PM"])),
            ("Dr. Priya Sharma", "Neurology",        json.dumps(["09:30 AM","10:30 AM","11:30 AM","01:30 PM","02:30 PM","03:30 PM"])),
            ("Dr. Rohan Gupta",  "Orthopedics",      json.dumps(["10:00 AM","11:00 AM","12:00 PM","02:00 PM","04:00 PM","05:00 PM"])),
            ("Dr. Sneha Verma",  "Dermatology",      json.dumps(["09:00 AM","10:00 AM","12:00 PM","01:00 PM","03:00 PM","05:00 PM"])),
            ("Dr. Kiran Patel",  "General Medicine", json.dumps(["08:00 AM","09:00 AM","10:00 AM","11:00 AM","02:00 PM","03:00 PM","04:00 PM","05:00 PM"])),
        ]
        cur.executemany(
            "INSERT INTO doctors (name, specialty, available_slots) VALUES (?,?,?)",
            doctors
        )

    conn.commit()
    conn.close()

init_db()

# ─────────────────────────────────────────────
#  AI Scheduling Engine
# ─────────────────────────────────────────────
def get_booked_slots(doctor_id, date):
    """Return list of time strings already booked for a doctor on a date."""
    conn = get_db()
    rows = conn.execute(
        "SELECT appointment_time FROM appointments WHERE doctor_id=? AND appointment_date=? AND status != 'Cancelled'",
        (doctor_id, date)
    ).fetchall()
    conn.close()
    return [r["appointment_time"] for r in rows]


def get_datetime_for_slot(date, time_str):
    try:
        return datetime.strptime(f"{date} {time_str}", "%Y-%m-%d %I:%M %p")
    except ValueError:
        return None


def predict_queue(date=None):
    """Estimate today’s queue load and wait time based on scheduled appointments."""
    date = date or datetime.now().strftime("%Y-%m-%d")
    now = datetime.now()
    conn = get_db()
    rows = conn.execute(
        "SELECT appointment_time FROM appointments WHERE appointment_date=? AND status != 'Cancelled'",
        (date,)
    ).fetchall()
    conn.close()

    appointment_times = [get_datetime_for_slot(date, r["appointment_time"]) for r in rows]
    appointment_times = [t for t in appointment_times if t is not None]
    upcoming = sorted([t for t in appointment_times if t >= now])

    upcoming_count = len(upcoming)
    predicted_wait = upcoming_count * APPOINTMENT_DURATION_MINUTES
    if upcoming_count == 0:
        wait_text = "No wait expected"
    elif predicted_wait < 30:
        wait_text = f"{predicted_wait} min"
    else:
        wait_text = f"{predicted_wait} min"

    if upcoming_count <= 3:
        load_level = "Low"
    elif upcoming_count <= 6:
        load_level = "Moderate"
    else:
        load_level = "High"

    next_slot = upcoming[0].strftime("%I:%M %p") if upcoming else "No open slots"
    return {
        "date": date,
        "upcoming_count": upcoming_count,
        "predicted_wait": predicted_wait,
        "predicted_wait_text": wait_text,
        "next_slot": next_slot,
        "load_level": load_level,
    }


def ai_recommend_slot(doctor_id, date):
    """
    AI recommendation logic:
    1. Fetch doctor's base slots.
    2. Remove already-booked slots for the requested date.
    3. Score remaining slots: morning slots preferred (productivity peak).
    4. Return top recommendation + all available slots.
    """
    conn = get_db()
    doctor = conn.execute("SELECT * FROM doctors WHERE id=?", (doctor_id,)).fetchone()
    conn.close()

    if not doctor:
        return None, []

    base_slots  = json.loads(doctor["available_slots"])
    booked      = get_booked_slots(doctor_id, date)
    available   = [s for s in base_slots if s not in booked]

    if not available:
        return "No Slots Available", []

    # Score: morning (AM) slots get +2, others +1; earlier = higher priority
    def score(slot):
        t = datetime.strptime(slot, "%I:%M %p")
        if t.hour < 12:
            return (0, t.hour, t.minute)   # morning first
        return (1, t.hour, t.minute)

    available_sorted = sorted(available, key=score)
    return available_sorted[0], available_sorted

def get_dashboard_stats():
    conn = get_db()
    total       = conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
    today       = datetime.now().strftime("%Y-%m-%d")
    today_count = conn.execute(
        "SELECT COUNT(*) FROM appointments WHERE appointment_date=?", (today,)
    ).fetchone()[0]
    confirmed   = conn.execute(
        "SELECT COUNT(*) FROM appointments WHERE status='Confirmed'"
    ).fetchone()[0]
    cancelled   = conn.execute(
        "SELECT COUNT(*) FROM appointments WHERE status='Cancelled'"
    ).fetchone()[0]
    conn.close()
    return {"total": total, "today": today_count, "confirmed": confirmed, "cancelled": cancelled}


# ─────────────────────────────────────────────
#  Routes
# ─────────────────────────────────────────────
@app.route('/')
def home():
    conn = get_db()
    doctors = conn.execute("SELECT * FROM doctors").fetchall()
    recent  = conn.execute('''
        SELECT a.*, d.name as doctor_name, d.specialty
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        ORDER BY a.created_at DESC LIMIT 5
    ''').fetchall()
    conn.close()

    stats = get_dashboard_stats()
    today = datetime.now().strftime("%Y-%m-%d")
    queue_stats = predict_queue(today)
    return render_template('index.html',
                           doctors=doctors,
                           recent=recent,
                           stats=stats,
                           today=today,
                           queue_stats=queue_stats)


@app.route('/api/slots')
def api_slots():
    """AJAX endpoint: returns AI-recommended slot + all available slots."""
    doctor_id = request.args.get('doctor_id', type=int)
    date      = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))

    if not doctor_id:
        return jsonify({"error": "Missing doctor_id"}), 400

    recommended, available = ai_recommend_slot(doctor_id, date)
    return jsonify({
        "recommended": recommended,
        "available":   available
    })


@app.route('/book', methods=['POST'])
def book():
    patient_name  = request.form['patient_name'].strip()
    patient_email = request.form.get('patient_email', '').strip()
    patient_phone = request.form.get('patient_phone', '').strip()
    doctor_id     = int(request.form['doctor_id'])
    appt_date     = request.form['appointment_date']
    appt_time     = request.form['appointment_time']
    reason        = request.form.get('reason', '').strip()

    # Conflict guard
    conn = get_db()
    conflict = conn.execute(
        "SELECT id FROM appointments WHERE doctor_id=? AND appointment_date=? AND appointment_time=? AND status!='Cancelled'",
        (doctor_id, appt_date, appt_time)
    ).fetchone()

    if conflict:
        conn.close()
        doctors = conn.execute("SELECT * FROM doctors").fetchall() if False else get_db().execute("SELECT * FROM doctors").fetchall()
        stats   = get_dashboard_stats()
        return render_template('index.html',
                               doctors=doctors,
                               stats=stats,
                               today=appt_date,
                               error="⚠️ That slot is already booked. Please choose another time.")

    conn.execute('''
        INSERT INTO appointments
            (patient_name, patient_email, patient_phone, doctor_id,
             appointment_date, appointment_time, reason)
        VALUES (?,?,?,?,?,?,?)
    ''', (patient_name, patient_email, patient_phone, doctor_id,
          appt_date, appt_time, reason))
    conn.commit()
    appt_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    doctor = conn.execute("SELECT * FROM doctors WHERE id=?", (doctor_id,)).fetchone()
    conn.close()

    return render_template('success.html',
                           patient_name=patient_name,
                           patient_email=patient_email,
                           doctor_name=doctor['name'],
                           specialty=doctor['specialty'],
                           appt_date=appt_date,
                           appt_time=appt_time,
                           appt_id=appt_id,
                           reason=reason)


@app.route('/appointments')
def appointments():
    conn = get_db()
    rows = conn.execute('''
        SELECT a.*, d.name as doctor_name, d.specialty
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        ORDER BY a.id ASC
    ''').fetchall()
    rows = sorted(rows, key=lambda row: row["id"])
    conn.close()
    stats = get_dashboard_stats()
    queue_stats = predict_queue()
    return render_template('appointments.html', appointments=rows, stats=stats, queue_stats=queue_stats)


@app.route('/cancel/<int:appt_id>', methods=['POST'])
def cancel(appt_id):
    conn = get_db()
    conn.execute("UPDATE appointments SET status='Cancelled' WHERE id=?", (appt_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('appointments'))


if __name__ == '__main__':
    app.run(debug=True)
