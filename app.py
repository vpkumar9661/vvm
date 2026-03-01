from flask_mail import Mail, Message
from flask import Flask, render_template, request, redirect, session
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ===============================
# MAIL CONFIG
# ===============================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'yourgmail@gmail.com'
app.config['MAIL_PASSWORD'] = 'your_app_password'

mail = Mail(app)

# ===============================
# HOME
# ===============================
@app.route("/")
def home():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    notices = conn.execute(
        "SELECT * FROM notices ORDER BY date DESC LIMIT 5"
    ).fetchall()

    gallery = conn.execute(
        "SELECT * FROM gallery ORDER BY RANDOM() LIMIT 6"
    ).fetchall()

    conn.close()

    return render_template("index.html",
                           notices=notices,
                           gallery=gallery)

# ===============================
# GALLERY PAGE
# ===============================
@app.route("/gallery")
def gallery_page():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    gallery = conn.execute(
        "SELECT * FROM gallery ORDER BY id DESC"
    ).fetchall()

    conn.close()

    return render_template("gallery.html", gallery=gallery)

# ===============================
# ADMISSION PAGE
# ===============================
@app.route("/admission")
def admission_page():
    return render_template("admission.html")


@app.route("/submit-admission", methods=["POST"])
def submit_admission():
    name = request.form["student_name"]
    father = request.form["father_name"]
    class_apply = request.form["class_apply"]
    dob = request.form["dob"]
    phone = request.form["phone"]
    email = request.form["email"]
    address = request.form["address"]

    conn = sqlite3.connect("database.db")
    conn.execute("""
        INSERT INTO admissions 
        (student_name, father_name, class_apply, dob, phone, email, address)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, father, class_apply, dob, phone, email, address))

    conn.commit()
    conn.close()

    return redirect("/admission")

# ===============================
# CONTACT FORM
# ===============================
@app.route("/send-message", methods=["POST"])
def send_message():
    name = request.form['name']
    email = request.form['email']
    message = request.form['message']

    msg = Message(
        subject=f"New Message from {name}",
        sender=app.config['MAIL_USERNAME'],
        recipients=["vvmdharampur@gmail.com"]
    )

    msg.body = f"""
    Name: {name}
    Email: {email}
    Message: {message}
    """

    mail.send(msg)
    return redirect("/")

# ===============================
# ADMIN LOGIN
# ===============================
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        admin = conn.execute(
            "SELECT * FROM admin WHERE username=? AND password=?",
            (username, password)
        ).fetchone()
        conn.close()

        if admin:
            session["admin"] = username
            return redirect("/dashboard")

    return render_template("admin_login.html")

@app.route("/dashboard")
def dashboard():
    if "admin" not in session:
        return redirect("/admin")

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    notices = c.execute(
        "SELECT * FROM notices ORDER BY date DESC"
    ).fetchall()

    gallery = c.execute(
        "SELECT * FROM gallery"
    ).fetchall()

    admissions = c.execute(
        "SELECT * FROM admissions ORDER BY id DESC"
    ).fetchall()

    # ✅ Analytics Counts (YAHI PAR HONA CHAHIYE)
    approved = c.execute(
        "SELECT COUNT(*) FROM admissions WHERE status='Approved'"
    ).fetchone()[0]

    rejected = c.execute(
        "SELECT COUNT(*) FROM admissions WHERE status='Rejected'"
    ).fetchone()[0]

    pending = c.execute(
        "SELECT COUNT(*) FROM admissions WHERE status='Pending'"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        notices=notices,
        gallery=gallery,
        admissions=admissions,
        approved=approved,
        rejected=rejected,
        pending=pending
    )


# ===============================
# NOTICE
# ===============================
@app.route("/add-notice", methods=["POST"])
def add_notice():
    if "admin" not in session:
        return redirect("/admin")

    title = request.form["title"]
    content = request.form["content"]
    image_file = request.files.get("image")

    image_name = None

    if image_file and image_file.filename != "":
        image_name = image_file.filename
        image_path = os.path.join("static/notice_images", image_name)
        image_file.save(image_path)

    conn = sqlite3.connect("database.db")
    conn.execute(
        "INSERT INTO notices (title, content, image) VALUES (?, ?, ?)",
        (title, content, image_name)
    )
    conn.commit()
    conn.close()

    return redirect("/dashboard")

@app.route("/delete-notice/<int:id>")
def delete_notice(id):
    if "admin" not in session:
        return redirect("/admin")

    conn = sqlite3.connect("database.db")
    conn.execute("DELETE FROM notices WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect("/dashboard")

# ===============================
# GALLERY UPLOAD
# ===============================
UPLOAD_FOLDER = os.path.join("static", "gallery")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

@app.route("/upload-gallery", methods=["POST"])
def upload_gallery():
    if "admin" not in session:
        return redirect("/admin")

    if not os.path.exists(app.config["UPLOAD_FOLDER"]):
        os.makedirs(app.config["UPLOAD_FOLDER"])

    file = request.files["image"]

    if file and file.filename != "":
        filename = file.filename
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        conn = sqlite3.connect("database.db")
        conn.execute(
            "INSERT INTO gallery (image) VALUES (?)",
            (filename,)
        )
        conn.commit()
        conn.close()

    return redirect("/dashboard")

@app.route("/delete-gallery/<int:id>")
def delete_gallery(id):
    if "admin" not in session:
        return redirect("/admin")

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    image = conn.execute(
        "SELECT image FROM gallery WHERE id=?",
        (id,)
    ).fetchone()

    if image:
        image_path = os.path.join("static/gallery", image["image"])
        if os.path.exists(image_path):
            os.remove(image_path)

        conn.execute("DELETE FROM gallery WHERE id=?", (id,))
        conn.commit()

    conn.close()
    return redirect("/dashboard")

# admission status email

@app.route("/update-admission-status", methods=["POST"])
def update_admission_status():

    if "admin" not in session:
        return redirect("/admin")

    id = request.form["id"]
    action = request.form["action"]

    status = "Approved" if action == "approve" else "Rejected"

    conn = sqlite3.connect("database.db")
    conn.execute("UPDATE admissions SET status=? WHERE id=?", (status, id))
    conn.commit()
    conn.close()

    return redirect("/dashboard")

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/")

# ===============================
# RUN APP (ALWAYS LAST)
# ===============================
if __name__ == "__main__":
    app.run(debug=True)


import os

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
