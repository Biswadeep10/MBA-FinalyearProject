# 🏥 MediSchedule AI — Healthcare Appointment Scheduling System

An AI-powered appointment scheduling system built for a **MBA Final Year Project** on Healthcare Operations Management. The system demonstrates how AI-driven slot recommendation reduces scheduling conflicts, minimises patient wait times, and improves overall operational efficiency in a hospital environment.

---

## 📌 Features

| Feature | Description |
|---|---|
| 🤖 AI Slot Recommendation | Scores and recommends the optimal available slot (morning-first heuristic) |
| 📅 Real-time Availability | Checks booked slots dynamically before showing options |
| 👨‍⚕️ Doctor Management | 5 pre-seeded doctors across specialties (Cardiology, Neurology, etc.) |
| 📋 Appointment Booking | Patients provide name, email, phone, doctor, date, time, and reason |
| 🚫 Conflict Prevention | Blocks double-booking the same doctor/date/time slot |
| 📊 Dashboard Stats | Live counts of total, today's, confirmed, and cancelled appointments |
| 🗂️ Appointments Log | Searchable and filterable table of all bookings |
| ❌ Cancellation | One-click appointment cancellation with status tracking |

---

## 🗂️ Project Structure

```
MBA-FinalyearProject/
│
├── app.py                  # Flask backend — routes, AI engine, DB logic
├── requirements.txt        # Python dependencies
├── .gitignore
├── README.md
│
├── templates/
│   ├── index.html          # Home page — booking form + stats dashboard
│   ├── success.html        # Booking confirmation page
│   └── appointments.html   # All appointments management page
│
└── static/
    └── style.css           # Premium dark-mode UI styles
```

---

## 🛠️ Tech Stack

- **Backend** — Python 3, Flask
- **Database** — SQLite (file-based, zero config)
- **Frontend** — HTML5, Vanilla CSS (glassmorphism dark theme), JavaScript (ES6)
- **Fonts** — Inter via Google Fonts

---

## 🚀 How to Spin Up the Project

### Prerequisites
- Python 3.8 or higher installed
- pip (comes with Python)

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd MBA-FinalyearProject
```

### 2. (Optional) Create a virtual environment
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the application
```bash
python app.py
```

### 5. Open in your browser
```
http://127.0.0.1:5000
```

The SQLite database (`appointments.db`) is created automatically on first run, and the five doctors are seeded instantly — no manual setup required.

---

## 🤖 AI Scheduling Logic

The recommendation engine in `app.py → ai_recommend_slot()` works as follows:

1. Fetches the selected doctor's full slot list
2. Queries the database for already-booked slots on the chosen date
3. Filters out unavailable slots
4. Scores remaining slots — **morning (AM) slots are prioritised** as research shows morning appointments correlate with higher patient satisfaction and lower no-show rates
5. Returns the top-scored slot as the AI recommendation alongside all available options

> *"The AI scheduling algorithm optimises appointment allocation and reduces operational conflicts through a time-preference scoring model."*

---

## 📄 MBA Project Context

This project was developed as part of an MBA Final Year Project exploring the application of AI and automation in **Healthcare Operations Management**. Key learning outcomes demonstrated:

- Process optimisation through intelligent scheduling
- Reduction of administrative overhead
- Real-time data-driven decision making
- Queue theory applied to appointment slot allocation

---

## 👨‍💻 Author

**Biswadeep** — MBA Final Year Student  
Healthcare Operations & AI Applications
