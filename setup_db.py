import sqlite3

conn = sqlite3.connect("database.db")
c = conn.cursor()

# Admin table
c.execute("""
CREATE TABLE IF NOT EXISTS admin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    password TEXT
)
""")

# Notices
c.execute("""
CREATE TABLE IF NOT EXISTS notices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    content TEXT,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Gallery
c.execute("""
CREATE TABLE IF NOT EXISTS gallery (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image TEXT
)
""")

# Counters
c.execute("""
CREATE TABLE IF NOT EXISTS counters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    students INTEGER,
    teachers INTEGER,
    classrooms INTEGER,
    experience INTEGER
)
""")

# Principal Message
c.execute("""
CREATE TABLE IF NOT EXISTS principal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT
)
""")

# Default Admin
c.execute("INSERT INTO admin (username, password) VALUES ('admin', 'admin123')")

conn.commit()
conn.close()
print("Database setup complete")