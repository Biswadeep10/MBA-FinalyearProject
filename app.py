from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
from datetime import datetime, timedelta
import json
import random

app = Flask(__name__)
DB_PATH = 'appointments.db'

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
#  Queue Prediction Module (AI)
# ─────────────────────────────────────────────
AVG_CONSULT_MINUTES = 15   # average consultation duration
BUFFER_MINUTES      = 5    # buffer between appointments

def predict_queue(doctor_id, date, selected_slot=None):
    """
    AI Queue Prediction Engine.
    For a given doctor and date, returns:
      - queue_position : how many patients are before the selected slot
      - estimated_wait : predicted wait in minutes
      - doctor_load    : percentage of slots booked (0-100)
      - load_label     : Low / Moderate / High / Full
      - patients_today : count of confirmed patients for the day
      - peak_hours     : busiest time window
    """
    conn = get_db()
    doctor = conn.execute("SELECT * FROM doctors WHERE id=?", (doctor_id,)).fetchone()
    if not doctor:
        conn.close()
        return None

    base_slots = json.loads(doctor["available_slots"])
    total_slots = len(base_slots)

    # Get all confirmed bookings for this doctor on this date
    booked_rows = conn.execute(
        "SELECT appointment_time FROM appointments WHERE doctor_id=? AND appointment_date=? AND status != 'Cancelled'",
        (doctor_id, date)
    ).fetchall()
    conn.close()

    booked_times = [r["appointment_time"] for r in booked_rows]
    patients_today = len(booked_times)

    # Doctor load percentage
    doctor_load = round((patients_today / total_slots) * 100) if total_slots > 0 else 0
    if doctor_load >= 100:
        load_label = "Full"
    elif doctor_load >= 70:
        load_label = "High"
    elif doctor_load >= 40:
        load_label = "Moderate"
    else:
        load_label = "Low"

    # Queue position for selected slot
    queue_position = 0
    estimated_wait = 0
    if selected_slot and selected_slot in base_slots:
        slot_index = base_slots.index(selected_slot)
        # Count how many booked slots come before the selected one
        for bt in booked_times:
            if bt in base_slots:
                if base_slots.index(bt) < slot_index:
                    queue_position += 1
        estimated_wait = queue_position * (AVG_CONSULT_MINUTES + BUFFER_MINUTES)
        # Add a small random factor to simulate real-world variance
        estimated_wait += random.randint(0, 5)

    # Find peak hours – the hour with the most bookings
    hour_counts = {}
    for bt in booked_times:
        try:
            h = datetime.strptime(bt, "%I:%M %p").hour
            hour_counts[h] = hour_counts.get(h, 0) + 1
        except ValueError:
            pass

    if hour_counts:
        peak_h = max(hour_counts, key=hour_counts.get)
        peak_hours = f"{peak_h}:00 – {peak_h + 1}:00"
    else:
        peak_hours = "No data yet"

    return {
        "queue_position":  queue_position,
        "estimated_wait":  estimated_wait,
        "doctor_load":     doctor_load,
        "load_label":      load_label,
        "patients_today":  patients_today,
        "total_slots":     total_slots,
        "peak_hours":      peak_hours
    }

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
    return render_template('index.html',
                           doctors=doctors,
                           recent=recent,
                           stats=stats,
                           today=today)


@app.route('/api/slots')
def api_slots():
    """AJAX endpoint: returns AI-recommended slot + all available slots."""
    doctor_id = request.args.get('doctor_id', type=int)
    date      = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))

    if not doctor_id:
        return jsonify({"error": "Missing doctor_id"}), 400

    recommended, available = ai_recommend_slot(doctor_id, date)
    queue = predict_queue(doctor_id, date, recommended)
    return jsonify({
        "recommended": recommended,
        "available":   available,
        "queue":       queue
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
        ORDER BY a.appointment_date DESC, a.appointment_time ASC
    ''').fetchall()
    conn.close()
    stats = get_dashboard_stats()
    return render_template('appointments.html', appointments=rows, stats=stats)


@app.route('/cancel/<int:appt_id>', methods=['POST'])
def cancel(appt_id):
    conn = get_db()
    conn.execute("UPDATE appointments SET status='Cancelled' WHERE id=?", (appt_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('appointments'))


@app.route('/api/queue')
def api_queue():
    """Standalone queue prediction endpoint."""
    doctor_id = request.args.get('doctor_id', type=int)
    date      = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))
    slot      = request.args.get('slot', '')

    if not doctor_id:
        return jsonify({"error": "Missing doctor_id"}), 400

    result = predict_queue(doctor_id, date, slot if slot else None)
    if result is None:
        return jsonify({"error": "Doctor not found"}), 404

    return jsonify(result)


if __name__ == '__main__':
    app.run(debug=True)
