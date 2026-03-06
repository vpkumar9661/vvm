from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import date, datetime
from typing import List
from io import BytesIO
from pathlib import Path

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
STUDENT_PHOTO_DIR = UPLOAD_DIR / "students"

app = Flask(__name__)
app.secret_key = "change-this-secret"


# -----------------------------
# DB helpers
# -----------------------------

def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    STUDENT_PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    conn = db_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admission_number TEXT UNIQUE NOT NULL,
            student_name TEXT NOT NULL,
            student_photo TEXT,
            father_name TEXT,
            mother_name TEXT,
            aadhar_card_number TEXT,
            mobile_number TEXT,
            address TEXT,
            dob TEXT,
            gender TEXT,
            class_name TEXT,
            section TEXT,
            roll_number TEXT,
            admission_date TEXT,
            transport_distance REAL DEFAULT 0,
            transport_fee REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS fee_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            fee_month TEXT NOT NULL,
            base_fee REAL NOT NULL,
            transport_fee REAL NOT NULL,
            late_fine REAL NOT NULL,
            total_paid REAL NOT NULL,
            paid_on TEXT NOT NULL,
            payment_mode TEXT,
            receipt_no TEXT UNIQUE NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(id)
        );

        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_name TEXT NOT NULL,
            subject TEXT,
            mobile_number TEXT,
            salary REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS teacher_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            paid_amount REAL NOT NULL,
            paid_on TEXT NOT NULL,
            UNIQUE(teacher_id, month),
            FOREIGN KEY(teacher_id) REFERENCES teachers(id)
        );

        CREATE TABLE IF NOT EXISTS exam_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT NOT NULL,
            exam_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            exam_date TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT
        );

        CREATE TABLE IF NOT EXISTS attendance_students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            attendance_date TEXT NOT NULL,
            status TEXT NOT NULL,
            UNIQUE(student_id, attendance_date),
            FOREIGN KEY(student_id) REFERENCES students(id)
        );

        CREATE TABLE IF NOT EXISTS attendance_teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            attendance_date TEXT NOT NULL,
            status TEXT NOT NULL,
            UNIQUE(teacher_id, attendance_date),
            FOREIGN KEY(teacher_id) REFERENCES teachers(id)
        );

        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            posted_on TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO admin_users(username, password) VALUES (?, ?)",
        ("admin", "admin123"),
    )
    conn.commit()
    conn.close()


@app.context_processor
def inject_globals():
    return {"today": date.today().isoformat()}


# -----------------------------
# Utility
# -----------------------------

def compute_transport_fee(distance: float) -> float:
    if distance <= 2:
        return 400
    if distance <= 5:
        return 700
    if distance <= 10:
        return 1000
    return 1400


def late_fine_for_month(month_key: str) -> float:
    # month_key format: YYYY-MM
    due_date = datetime.strptime(f"{month_key}-10", "%Y-%m-%d").date()
    delay_days = max((date.today() - due_date).days, 0)
    if delay_days <= 0:
        return 0.0
    return min(delay_days * 10, 1000)


def build_simple_pdf(lines: List[str], title: str = "School ERP") -> bytes:
    safe_lines = [title] + lines
    y = 800
    content_lines = ["BT /F1 14 Tf 50 820 Td ({}) Tj ET".format(title.replace('(', '[').replace(')', ']'))]
    for line in lines:
        line = line.replace('(', '[').replace(')', ']')[:110]
        content_lines.append(f"BT /F1 10 Tf 50 {y} Td ({line}) Tj ET")
        y -= 16
        if y < 60:
            break
    stream = "\n".join(content_lines).encode('latin-1', 'ignore')

    objects = []
    objects.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    objects.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
    objects.append(b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n")
    objects.append(b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")
    objects.append(f"5 0 obj << /Length {len(stream)} >> stream\n".encode() + stream + b"\nendstream endobj\n")

    pdf = b"%PDF-1.4\n"
    offsets = []
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj
    xref_pos = len(pdf)
    pdf += f"xref\n0 {len(objects)+1}\n".encode()
    pdf += b"0000000000 65535 f \n"
    for off in offsets:
        pdf += f"{off:010} 00000 n \n".encode()
    pdf += f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode()
    return pdf


def month_name(month_key: str) -> str:
    return datetime.strptime(month_key, "%Y-%m").strftime("%b %Y")


def login_required():
    return "admin_user" in session


# -----------------------------
# Auth & Dashboard
# -----------------------------
@app.route("/")
def index():
    if login_required():
        return redirect(url_for("dashboard"))
    return redirect(url_for("admin_login"))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        conn = db_conn()
        user = conn.execute(
            "SELECT * FROM admin_users WHERE username=? AND password=?",
            (username, password),
        ).fetchone()
        conn.close()

        if user:
            session["admin_user"] = username
            return redirect(url_for("dashboard"))

        flash("Invalid credentials", "danger")

    return render_template("admin_login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect(url_for("admin_login"))

    month_key = date.today().strftime("%Y-%m")
    conn = db_conn()

    student_count = conn.execute("SELECT COUNT(*) c FROM students").fetchone()["c"]
    teacher_count = conn.execute("SELECT COUNT(*) c FROM teachers").fetchone()["c"]

    expected_fees = conn.execute(
        "SELECT COALESCE(SUM(2000 + transport_fee),0) total FROM students"
    ).fetchone()["total"]

    received_this_month = conn.execute(
        "SELECT COALESCE(SUM(total_paid),0) total FROM fee_payments WHERE fee_month=?",
        (month_key,),
    ).fetchone()["total"]

    pending_fees = max(expected_fees - received_this_month, 0)

    monthly_income = conn.execute(
        """
        SELECT fee_month, COALESCE(SUM(total_paid),0) total
        FROM fee_payments
        GROUP BY fee_month
        ORDER BY fee_month
        LIMIT 12
        """
    ).fetchall()

    total_income = conn.execute(
        "SELECT COALESCE(SUM(total_paid),0) total FROM fee_payments"
    ).fetchone()["total"]

    last_transactions = conn.execute(
        """
        SELECT fp.*, s.student_name, s.admission_number
        FROM fee_payments fp
        JOIN students s ON s.id = fp.student_id
        ORDER BY fp.id DESC
        LIMIT 30
        """
    ).fetchall()

    notices = conn.execute(
        "SELECT * FROM notices ORDER BY id DESC LIMIT 5"
    ).fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        student_count=student_count,
        teacher_count=teacher_count,
        expected_fees=expected_fees,
        received_this_month=received_this_month,
        pending_fees=pending_fees,
        total_income=total_income,
        monthly_income=monthly_income,
        last_transactions=last_transactions,
        notices=notices,
        month_key=month_key,
    )


# -----------------------------
# Student admission management
# -----------------------------
@app.route("/students")
def students():
    if not login_required():
        return redirect(url_for("admin_login"))

    search = request.args.get("search", "").strip()
    class_filter = request.args.get("class", "").strip()

    query = "SELECT * FROM students WHERE 1=1"
    params: List[str] = []

    if search:
        query += " AND (student_name LIKE ? OR admission_number LIKE ? OR mobile_number LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])

    if class_filter:
        query += " AND class_name=?"
        params.append(class_filter)

    query += " ORDER BY id DESC"

    conn = db_conn()
    rows = conn.execute(query, params).fetchall()
    classes = conn.execute("SELECT DISTINCT class_name FROM students WHERE class_name != '' ORDER BY class_name").fetchall()
    conn.close()

    return render_template("students.html", students=rows, classes=classes, search=search, class_filter=class_filter)


@app.route("/students/add", methods=["GET", "POST"])
def add_student():
    if not login_required():
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        form = request.form
        distance = float(form.get("transport_distance") or 0)
        transport_fee = compute_transport_fee(distance)

        photo_file = request.files.get("student_photo")
        photo_name = ""
        if photo_file and photo_file.filename:
            safe_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{photo_file.filename}"
            photo_path = STUDENT_PHOTO_DIR / safe_name
            photo_file.save(photo_path)
            photo_name = safe_name

        conn = db_conn()
        try:
            conn.execute(
                """
                INSERT INTO students (
                    admission_number, student_name, student_photo, father_name, mother_name,
                    aadhar_card_number, mobile_number, address, dob, gender,
                    class_name, section, roll_number, admission_date,
                    transport_distance, transport_fee
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    form.get("admission_number"),
                    form.get("student_name"),
                    photo_name,
                    form.get("father_name"),
                    form.get("mother_name"),
                    form.get("aadhar_card_number"),
                    form.get("mobile_number"),
                    form.get("address"),
                    form.get("dob"),
                    form.get("gender"),
                    form.get("class_name"),
                    form.get("section"),
                    form.get("roll_number"),
                    form.get("admission_date"),
                    distance,
                    transport_fee,
                ),
            )
            conn.commit()
            flash("Student added successfully", "success")
        except sqlite3.IntegrityError:
            flash("Admission number already exists", "danger")
        finally:
            conn.close()

        return redirect(url_for("students"))

    return render_template("student_form.html", student=None)


@app.route("/students/edit/<int:student_id>", methods=["GET", "POST"])
def edit_student(student_id: int):
    if not login_required():
        return redirect(url_for("admin_login"))

    conn = db_conn()
    student = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    if not student:
        conn.close()
        flash("Student not found", "danger")
        return redirect(url_for("students"))

    if request.method == "POST":
        form = request.form
        distance = float(form.get("transport_distance") or 0)
        transport_fee = compute_transport_fee(distance)
        photo_name = student["student_photo"]

        photo_file = request.files.get("student_photo")
        if photo_file and photo_file.filename:
            safe_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{photo_file.filename}"
            photo_file.save(STUDENT_PHOTO_DIR / safe_name)
            photo_name = safe_name

        conn.execute(
            """
            UPDATE students SET
                admission_number=?, student_name=?, student_photo=?, father_name=?, mother_name=?,
                aadhar_card_number=?, mobile_number=?, address=?, dob=?, gender=?,
                class_name=?, section=?, roll_number=?, admission_date=?,
                transport_distance=?, transport_fee=?
            WHERE id=?
            """,
            (
                form.get("admission_number"), form.get("student_name"), photo_name,
                form.get("father_name"), form.get("mother_name"), form.get("aadhar_card_number"),
                form.get("mobile_number"), form.get("address"), form.get("dob"), form.get("gender"),
                form.get("class_name"), form.get("section"), form.get("roll_number"), form.get("admission_date"),
                distance, transport_fee, student_id,
            ),
        )
        conn.commit()
        conn.close()
        flash("Student updated", "success")
        return redirect(url_for("students"))

    conn.close()
    return render_template("student_form.html", student=student)


@app.route("/students/delete/<int:student_id>")
def delete_student(student_id: int):
    if not login_required():
        return redirect(url_for("admin_login"))

    conn = db_conn()
    conn.execute("DELETE FROM students WHERE id=?", (student_id,))
    conn.commit()
    conn.close()
    flash("Student deleted", "warning")
    return redirect(url_for("students"))


# -----------------------------
# Fee management
# -----------------------------
@app.route("/fees", methods=["GET", "POST"])
def fees():
    if not login_required():
        return redirect(url_for("admin_login"))

    conn = db_conn()
    students_list = conn.execute("SELECT id, student_name, admission_number, class_name, transport_fee FROM students ORDER BY student_name").fetchall()

    if request.method == "POST":
        student_id = int(request.form.get("student_id"))
        fee_month = request.form.get("fee_month")
        base_fee = float(request.form.get("base_fee") or 0)
        payment_mode = request.form.get("payment_mode")

        student = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
        if not student:
            flash("Student not found", "danger")
            conn.close()
            return redirect(url_for("fees"))

        late_fine = late_fine_for_month(fee_month)
        transport_fee = student["transport_fee"] or 0
        total_paid = base_fee + transport_fee + late_fine
        receipt_no = f"RCPT-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        conn.execute(
            """
            INSERT INTO fee_payments (
                student_id, fee_month, base_fee, transport_fee, late_fine,
                total_paid, paid_on, payment_mode, receipt_no
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                student_id,
                fee_month,
                base_fee,
                transport_fee,
                late_fine,
                total_paid,
                date.today().isoformat(),
                payment_mode,
                receipt_no,
            ),
        )
        conn.commit()
        conn.close()

        # SMS simulation
        flash(f"Fee paid. SMS sent to {student['mobile_number'] or 'N/A'} (simulated).", "success")
        return redirect(url_for("receipt_pdf", receipt_no=receipt_no))

    fee_history = conn.execute(
        """
        SELECT fp.*, s.student_name, s.admission_number
        FROM fee_payments fp
        JOIN students s ON s.id = fp.student_id
        ORDER BY fp.id DESC
        LIMIT 30
        """
    ).fetchall()
    conn.close()

    return render_template("fees.html", students=students_list, fee_history=fee_history)


@app.route("/receipt/<receipt_no>.pdf")
def receipt_pdf(receipt_no: str):
    if not login_required():
        return redirect(url_for("admin_login"))

    conn = db_conn()
    payment = conn.execute(
        """
        SELECT fp.*, s.student_name, s.admission_number, s.class_name, s.section
        FROM fee_payments fp
        JOIN students s ON s.id = fp.student_id
        WHERE fp.receipt_no=?
        """,
        (receipt_no,),
    ).fetchone()
    conn.close()

    if not payment:
        return "Receipt not found", 404

    lines = [
        f"Receipt No: {payment['receipt_no']}",
        f"Student: {payment['student_name']} ({payment['admission_number']})",
        f"Class: {payment['class_name']} {payment['section']}",
        f"Month: {month_name(payment['fee_month'])}",
        f"Base Fee: Rs. {payment['base_fee']:.2f}",
        f"Transport Fee: Rs. {payment['transport_fee']:.2f}",
        f"Late Fine: Rs. {payment['late_fine']:.2f}",
        f"Total Paid: Rs. {payment['total_paid']:.2f}",
        f"Paid On: {payment['paid_on']} | Mode: {payment['payment_mode']}",
    ]
    pdf_bytes = build_simple_pdf(lines, "School ERP Fee Receipt")
    return send_file(BytesIO(pdf_bytes), mimetype="application/pdf", as_attachment=True, download_name=f"{receipt_no}.pdf")


# -----------------------------
# Teacher payment management
# -----------------------------
@app.route("/teachers", methods=["GET", "POST"])
def teachers():
    if not login_required():
        return redirect(url_for("admin_login"))

    conn = db_conn()

    if request.method == "POST":
        conn.execute(
            "INSERT INTO teachers (teacher_name, subject, mobile_number, salary) VALUES (?, ?, ?, ?)",
            (
                request.form.get("teacher_name"),
                request.form.get("subject"),
                request.form.get("mobile_number"),
                float(request.form.get("salary") or 0),
            ),
        )
        conn.commit()
        flash("Teacher added", "success")

    teachers_list = conn.execute("SELECT * FROM teachers ORDER BY teacher_name").fetchall()

    month_filter = request.args.get("month") or date.today().strftime("%Y-%m")
    payments = conn.execute(
        """
        SELECT tp.*, t.teacher_name, t.salary
        FROM teacher_payments tp
        JOIN teachers t ON t.id = tp.teacher_id
        WHERE tp.month=?
        ORDER BY tp.id DESC
        """,
        (month_filter,),
    ).fetchall()

    due_list = conn.execute(
        """
        SELECT t.*
        FROM teachers t
        WHERE t.id NOT IN (
            SELECT teacher_id FROM teacher_payments WHERE month=?
        )
        ORDER BY t.teacher_name
        """,
        (month_filter,),
    ).fetchall()

    conn.close()
    return render_template("teachers.html", teachers=teachers_list, payments=payments, due_list=due_list, month_filter=month_filter)


@app.route("/teachers/pay", methods=["POST"])
def pay_teacher():
    if not login_required():
        return redirect(url_for("admin_login"))

    teacher_id = int(request.form.get("teacher_id"))
    month = request.form.get("month")
    amount = float(request.form.get("paid_amount") or 0)

    conn = db_conn()
    try:
        conn.execute(
            "INSERT INTO teacher_payments (teacher_id, month, paid_amount, paid_on) VALUES (?, ?, ?, ?)",
            (teacher_id, month, amount, date.today().isoformat()),
        )
        conn.commit()
        flash("Salary paid", "success")
    except sqlite3.IntegrityError:
        flash("Salary already paid for this teacher and month", "warning")
    finally:
        conn.close()

    return redirect(url_for("teachers", month=month))


# -----------------------------
# ID card generator
# -----------------------------
@app.route("/id-cards")
def id_cards():
    if not login_required():
        return redirect(url_for("admin_login"))

    conn = db_conn()
    classes = conn.execute("SELECT DISTINCT class_name FROM students ORDER BY class_name").fetchall()
    conn.close()
    return render_template("id_cards.html", classes=classes)


@app.route("/id-cards/download")
def id_cards_download():
    if not login_required():
        return redirect(url_for("admin_login"))

    class_name = request.args.get("class_name", "")

    conn = db_conn()
    rows = conn.execute("SELECT * FROM students WHERE class_name=? ORDER BY roll_number", (class_name,)).fetchall()
    conn.close()

    lines = [f"Class: {class_name} | Total Students: {len(rows)}"]
    for st in rows:
        lines.append(f"{st['student_name']} | Roll {st['roll_number']} | Adm {st['admission_number']} | Logo:[School Logo]")

    pdf_bytes = build_simple_pdf(lines, "Student ID Cards")
    return send_file(BytesIO(pdf_bytes), mimetype="application/pdf", as_attachment=True, download_name=f"id_cards_{class_name}.pdf")


# -----------------------------
# Exam schedule
# -----------------------------
@app.route("/exams", methods=["GET", "POST"])
def exams():
    if not login_required():
        return redirect(url_for("admin_login"))

    conn = db_conn()
    if request.method == "POST":
        conn.execute(
            """
            INSERT INTO exam_schedules (class_name, exam_name, subject, exam_date, start_time, end_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                request.form.get("class_name"),
                request.form.get("exam_name"),
                request.form.get("subject"),
                request.form.get("exam_date"),
                request.form.get("start_time"),
                request.form.get("end_time"),
            ),
        )
        conn.commit()
        flash("Exam schedule added", "success")

    class_filter = request.args.get("class")
    if class_filter:
        schedules = conn.execute(
            "SELECT * FROM exam_schedules WHERE class_name=? ORDER BY exam_date",
            (class_filter,),
        ).fetchall()
    else:
        schedules = conn.execute("SELECT * FROM exam_schedules ORDER BY exam_date").fetchall()

    classes = conn.execute("SELECT DISTINCT class_name FROM students ORDER BY class_name").fetchall()
    conn.close()
    return render_template("exams.html", schedules=schedules, classes=classes, class_filter=class_filter)


@app.route("/exams/delete/<int:schedule_id>")
def delete_exam(schedule_id: int):
    if not login_required():
        return redirect(url_for("admin_login"))

    conn = db_conn()
    conn.execute("DELETE FROM exam_schedules WHERE id=?", (schedule_id,))
    conn.commit()
    conn.close()
    flash("Exam schedule removed", "warning")
    return redirect(url_for("exams"))


# -----------------------------
# Attendance & notices
# -----------------------------
@app.route("/attendance", methods=["GET", "POST"])
def attendance():
    if not login_required():
        return redirect(url_for("admin_login"))

    conn = db_conn()
    if request.method == "POST":
        record_type = request.form.get("record_type")
        person_id = int(request.form.get("person_id"))
        att_date = request.form.get("attendance_date")
        status = request.form.get("status")

        table = "attendance_students" if record_type == "student" else "attendance_teachers"
        column = "student_id" if record_type == "student" else "teacher_id"
        conn.execute(
            f"INSERT OR REPLACE INTO {table} ({column}, attendance_date, status) VALUES (?, ?, ?)",
            (person_id, att_date, status),
        )
        conn.commit()
        flash("Attendance saved", "success")

    students_list = conn.execute("SELECT id, student_name FROM students ORDER BY student_name").fetchall()
    teachers_list = conn.execute("SELECT id, teacher_name FROM teachers ORDER BY teacher_name").fetchall()

    recent_student_att = conn.execute(
        """
        SELECT a.*, s.student_name
        FROM attendance_students a
        JOIN students s ON s.id = a.student_id
        ORDER BY a.id DESC LIMIT 20
        """
    ).fetchall()

    recent_teacher_att = conn.execute(
        """
        SELECT a.*, t.teacher_name
        FROM attendance_teachers a
        JOIN teachers t ON t.id = a.teacher_id
        ORDER BY a.id DESC LIMIT 20
        """
    ).fetchall()

    conn.close()
    return render_template(
        "attendance.html",
        students=students_list,
        teachers=teachers_list,
        recent_student_att=recent_student_att,
        recent_teacher_att=recent_teacher_att,
    )


@app.route("/notices", methods=["GET", "POST"])
def notices():
    if not login_required():
        return redirect(url_for("admin_login"))

    conn = db_conn()
    if request.method == "POST":
        conn.execute(
            "INSERT INTO notices (title, content, posted_on) VALUES (?, ?, ?)",
            (request.form.get("title"), request.form.get("content"), date.today().isoformat()),
        )
        conn.commit()
        flash("Notice posted", "success")

    rows = conn.execute("SELECT * FROM notices ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("notices.html", notices=rows)


# -----------------------------
# Reports + backup
# -----------------------------
@app.route("/reports")
def reports():
    if not login_required():
        return redirect(url_for("admin_login"))

    class_name = request.args.get("class_name", "")
    student_id = request.args.get("student_id", "")
    month = request.args.get("month", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    query = """
        SELECT fp.*, s.student_name, s.admission_number, s.class_name
        FROM fee_payments fp
        JOIN students s ON s.id = fp.student_id
        WHERE 1=1
    """
    params: List[str] = []

    if class_name:
        query += " AND s.class_name=?"
        params.append(class_name)
    if student_id:
        query += " AND s.id=?"
        params.append(student_id)
    if month:
        query += " AND fp.fee_month=?"
        params.append(month)
    if start_date:
        query += " AND fp.paid_on>=?"
        params.append(start_date)
    if end_date:
        query += " AND fp.paid_on<=?"
        params.append(end_date)

    query += " ORDER BY fp.paid_on DESC"

    conn = db_conn()
    rows = conn.execute(query, params).fetchall()
    classes = conn.execute("SELECT DISTINCT class_name FROM students ORDER BY class_name").fetchall()
    students_list = conn.execute("SELECT id, student_name FROM students ORDER BY student_name").fetchall()
    conn.close()

    return render_template(
        "reports.html",
        rows=rows,
        classes=classes,
        students=students_list,
        filters={
            "class_name": class_name,
            "student_id": student_id,
            "month": month,
            "start_date": start_date,
            "end_date": end_date,
        },
    )


@app.route("/reports/export/pdf")
def reports_pdf():
    if not login_required():
        return redirect(url_for("admin_login"))

    conn = db_conn()
    rows = conn.execute(
        """
        SELECT fp.fee_month, fp.total_paid, fp.paid_on, s.student_name, s.class_name
        FROM fee_payments fp
        JOIN students s ON s.id = fp.student_id
        ORDER BY fp.id DESC LIMIT 100
        """
    ).fetchall()
    conn.close()

    lines = [
        f"{r['paid_on']} | {r['student_name']} | {r['class_name']} | {r['fee_month']} | Rs.{r['total_paid']:.0f}"
        for r in rows
    ]
    pdf_bytes = build_simple_pdf(lines, "School ERP Fee Report")
    return send_file(BytesIO(pdf_bytes), mimetype="application/pdf", as_attachment=True, download_name="fee_report.pdf")


@app.route("/reports/export/excel")
def reports_excel():
    if not login_required():
        return redirect(url_for("admin_login"))

    conn = db_conn()
    rows = conn.execute(
        """
        SELECT fp.fee_month, fp.base_fee, fp.transport_fee, fp.late_fine, fp.total_paid, fp.paid_on,
               s.student_name, s.admission_number, s.class_name
        FROM fee_payments fp
        JOIN students s ON s.id = fp.student_id
        ORDER BY fp.id DESC
        """
    ).fetchall()
    conn.close()

    output = BytesIO()
    text = "Paid On,Month,Student,Admission No,Class,Base,Transport,Late Fine,Total\n"
    for r in rows:
        text += f"{r['paid_on']},{r['fee_month']},{r['student_name']},{r['admission_number']},{r['class_name']},{r['base_fee']},{r['transport_fee']},{r['late_fine']},{r['total_paid']}\n"
    output.write(text.encode())
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="fee_report.csv", mimetype="text/csv")


@app.route("/backup")
def backup_db():
    if not login_required():
        return redirect(url_for("admin_login"))

    backup_name = f"school_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    backup_path = BASE_DIR / backup_name
    shutil.copy(DB_PATH, backup_path)
    return send_file(backup_path, as_attachment=True, download_name=backup_name)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
else:
    init_db()
