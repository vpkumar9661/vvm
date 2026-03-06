# Professional School ERP (Flask + SQLite)

Yeh project ek **school ERP web application** ka production-style starter hai jisme admission, fees, salary, attendance, reports aur dashboard modules available hain.

## ✅ Included Modules

- Student Admission System (Add/Edit/Delete/Search/Class filter)
- Fee Management (monthly fee, late fine auto-calc, fee history)
- Receipt PDF generation
- Transport fee by distance slabs
- Teacher Payment Management + due salary + monthly report
- Dashboard with KPI cards + Chart.js graphs
- ID Card Generator (class-wise PDF)
- Exam Schedule system
- Reports with filters + PDF/Excel export
- Attendance (student + teacher)
- Notice board
- Database backup download

## Tech Stack

- Backend: Python Flask
- Database: SQLite (default)
- Frontend: HTML/CSS/JavaScript + Bootstrap 5
- Charts: Chart.js
- PDF: Lightweight built-in PDF generator
- Excel: CSV export (Excel compatible)

---

## Non-coder Friendly Roadmap (VS Code ke liye)

### 1) Folder structure samjho

```
/workspace/vvm
├── app.py
├── requirements.txt
├── setup_db.py
├── database.db (auto create/update)
├── templates/
│   ├── base.html
│   ├── admin_login.html
│   ├── dashboard.html
│   ├── students.html
│   ├── student_form.html
│   ├── fees.html
│   ├── teachers.html
│   ├── attendance.html
│   ├── notices.html
│   ├── exams.html
│   ├── id_cards.html
│   └── reports.html
└── static/
    └── uploads/students/
```

### 2) VS Code me open karo
- VS Code open karo
- `File > Open Folder` -> project folder choose karo

### 3) Virtual environment banao
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 4) Dependencies install karo
```bash
pip install -r requirements.txt
```

### 5) Database initialize karo
```bash
python setup_db.py
```

### 6) Project run karo
```bash
python app.py
```
Browser me open karo: `http://127.0.0.1:5000`

### 7) Login details
- Username: `admin`
- Password: `admin123`

---

## Future Production Upgrade Suggestions

- Password hashing (Flask-Login + werkzeug security)
- Role based login (Admin / Accountant / Teacher)
- Real SMS API (Fast2SMS/Twilio)
- Cloud backup + scheduler
- MySQL migration
- REST API + mobile app integration

