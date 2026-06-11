# reset_admin_password.py

import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect("database.db")

conn.execute("""
    UPDATE users
    SET password = ?
    WHERE username = 'admin'
""", (generate_password_hash("PQO4WMly5P8Z"),))

conn.commit()
conn.close()

print("Đã reset password admin về PQO4WMly5P8Z")