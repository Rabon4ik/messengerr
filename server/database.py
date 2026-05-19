import sqlite3
import hashlib
import threading
from datetime import datetime


class Database:
    def __init__(self, db_path="data/messenger.db"):
        self.db_path = db_path
        self._local = threading.local()
        self.create_tables()

    @property
    def conn(self):
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

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
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                creator TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS group_members (
                group_id INTEGER,
                username TEXT,
                role TEXT DEFAULT 'member',   -- 'admin' или 'member'
                PRIMARY KEY (group_id, username),
                FOREIGN KEY (group_id) REFERENCES groups(id)
            );
            CREATE TABLE IF NOT EXISTS group_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                sender TEXT,
                content TEXT,
                timestamp TEXT,
                FOREIGN KEY (group_id) REFERENCES groups(id)
            );
        ''')
        self.conn.commit()

    # ─── Пользователи ─────────────────────────────────────────────────────────

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

    def user_exists(self, username: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM users WHERE username=?", (username,)
        ).fetchone() is not None

    def get_all_users(self):
        return [row[0] for row in self.conn.execute("SELECT username FROM users").fetchall()]

    # ─── Личные сообщения ─────────────────────────────────────────────────────

    def save_message(self, sender: str, receiver: str, content: str):
        self.conn.execute(
            "INSERT INTO messages (sender, receiver, content, timestamp) VALUES (?,?,?,?)",
            (sender, receiver, content, datetime.now().isoformat())
        )
        self.conn.commit()

    def get_history(self, user1: str, user2: str):
        rows = self.conn.execute("""
            SELECT sender, content, timestamp
            FROM messages
            WHERE (sender=? AND receiver=?) OR (sender=? AND receiver=?)
            ORDER BY timestamp
        """, (user1, user2, user2, user1)).fetchall()
        return [{"from": row[0], "content": row[1], "time": row[2]} for row in rows]

    def get_user_chats(self, username: str):
        rows = self.conn.execute("""
            SELECT DISTINCT
                CASE WHEN sender=? THEN receiver ELSE sender END as chat_user
            FROM messages
            WHERE sender=? OR receiver=?
            ORDER BY chat_user
        """, (username, username, username)).fetchall()
        return [row[0] for row in rows]

    # ─── Группы ───────────────────────────────────────────────────────────────

    def create_group(self, name: str, creator: str, members: list) -> int:
        """Создаёт группу, возвращает group_id."""
        cur = self.conn.execute(
            "INSERT INTO groups (name, creator, created_at) VALUES (?,?,?)",
            (name, creator, datetime.now().isoformat())
        )
        group_id = cur.lastrowid
        # Создатель — админ
        self.conn.execute(
            "INSERT INTO group_members (group_id, username, role) VALUES (?,?,?)",
            (group_id, creator, 'admin')
        )
        for member in members:
            if member != creator and self.user_exists(member):
                self.conn.execute(
                    "INSERT OR IGNORE INTO group_members (group_id, username, role) VALUES (?,?,?)",
                    (group_id, member, 'member')
                )
        self.conn.commit()
        return group_id

    def get_group(self, group_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT id, name, creator FROM groups WHERE id=?", (group_id,)
        ).fetchone()
        if not row:
            return None
        members = self.get_group_members(group_id)
        return {"id": row[0], "name": row[1], "creator": row[2], "members": members}

    def get_group_members(self, group_id: int) -> list:
        rows = self.conn.execute(
            "SELECT username, role FROM group_members WHERE group_id=?", (group_id,)
        ).fetchall()
        return [{"username": row[0], "role": row[1]} for row in rows]

    def get_user_groups(self, username: str) -> list:
        rows = self.conn.execute("""
            SELECT g.id, g.name, g.creator
            FROM groups g
            JOIN group_members gm ON g.id = gm.group_id
            WHERE gm.username=?
            ORDER BY g.name
        """, (username,)).fetchall()
        result = []
        for row in rows:
            members = self.get_group_members(row[0])
            result.append({"id": row[0], "name": row[1], "creator": row[2], "members": members})
        return result

    def is_group_member(self, group_id: int, username: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM group_members WHERE group_id=? AND username=?",
            (group_id, username)
        ).fetchone() is not None

    def is_group_admin(self, group_id: int, username: str) -> bool:
        row = self.conn.execute(
            "SELECT role FROM group_members WHERE group_id=? AND username=?",
            (group_id, username)
        ).fetchone()
        return row is not None and row[0] == 'admin'

    def add_group_member(self, group_id: int, username: str) -> bool:
        if not self.user_exists(username):
            return False
        try:
            self.conn.execute(
                "INSERT INTO group_members (group_id, username, role) VALUES (?,?,?)",
                (group_id, username, 'member')
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # уже в группе

    def kick_group_member(self, group_id: int, username: str):
        self.conn.execute(
            "DELETE FROM group_members WHERE group_id=? AND username=?",
            (group_id, username)
        )
        self.conn.commit()

    def rename_group(self, group_id: int, new_name: str):
        self.conn.execute(
            "UPDATE groups SET name=? WHERE id=?", (new_name, group_id)
        )
        self.conn.commit()

    def save_group_message(self, group_id: int, sender: str, content: str):
        self.conn.execute(
            "INSERT INTO group_messages (group_id, sender, content, timestamp) VALUES (?,?,?,?)",
            (group_id, sender, content, datetime.now().isoformat())
        )
        self.conn.commit()

    def get_group_history(self, group_id: int) -> list:
        rows = self.conn.execute("""
            SELECT sender, content, timestamp
            FROM group_messages
            WHERE group_id=?
            ORDER BY timestamp
        """, (group_id,)).fetchall()
        return [{"from": row[0], "content": row[1], "time": row[2]} for row in rows]