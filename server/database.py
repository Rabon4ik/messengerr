import sqlite3
import hashlib
from datetime import datetime

class Database:
    def __init__(self, db_path="data/messenger.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT,
                receiver TEXT,
                content TEXT,
                timestamp TEXT
            );
        ''')
        self.conn.commit()

    def register_user(self, username: str, password: str) -> bool:
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        try:
            self.conn.execute("INSERT INTO users VALUES (?, ?)", (username, pw_hash))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def check_login(self, username: str, password: str) -> bool:
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        result = self.conn.execute(
            "SELECT 1 FROM users WHERE username=? AND password_hash=?", 
            (username, pw_hash)
        ).fetchone()
        return result is not None

    def save_message(self, sender: str, receiver: str, content: str):
        self.conn.execute(
            "INSERT INTO messages (sender, receiver, content, timestamp) VALUES (?,?,?,?)",
            (sender, receiver, content, datetime.now().isoformat())
        )
        self.conn.commit()

    def get_history(self, user1: str, user2: str):
        rows = self.conn.execute("""
            SELECT sender, content, timestamp FROM messages 
            WHERE (sender=? AND receiver=?) OR (sender=? AND receiver=?)
            ORDER BY timestamp
        """, (user1, user2, user2, user1)).fetchall()
        return [{"from": r[0], "content": r[1], "time": r[2]} for r in rows]

    def get_all_users(self):
        return [row[0] for row in self.conn.execute("SELECT username FROM users").fetchall()]