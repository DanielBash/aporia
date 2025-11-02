import os
import sqlite3


class Database:
    def __init__(self, conf):
        self.path = conf.paths.database_dir
        self.conf = conf
        self.api = conf.api
        self.load()

    def load(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        conn = sqlite3.connect(str(self.path))
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        about TEXT,
        last_online TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );""")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        ready BOOLEAN DEFAULT TRUE);
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
        user_id INTEGER,
        token TEXT NOT NULL,
        cluster_token TEXT NOT NULL,
        about TEXT);
        """)
        conn.commit()
        conn.close()
        self.auth()

    def auth(self, force=False):
        if not self.session_available() or force:
            self.clear_table('sessions')
            try:
                data = self.api.auth()['response']
                self.add_row('sessions', {'user_id': data['user_id'], 'token': data['user_token'], 'cluster_token': data['cluster_token']})
                self.conf.notification_manager.show_notification(title='Апория', text='Создан новый пользователь')
                self.conf.api_auth = True
            except Exception:
                return "Couldn't authorize"
        self.conf.api_auth = True

    def add_row(self, table, data):
        columns = data.keys()
        columns_str = '(' + ', '.join(['?'] * len(columns)) + ')'
        vals = tuple(data.values())
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        cursor.execute(f"INSERT INTO {table} ({', '.join(columns)}) VALUES {columns_str}", vals)
        conn.commit()
        conn.close()

    def clear_table(self, name):
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {name};")
        conn.commit()
        conn.close()

    def session_available(self):
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sessions;")
        c = cursor.fetchone()[0]
        conn.close()
        return c > 0

    def get_all(self):
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions;")
        c = cursor.fetchone()
        conn.close()
        data = self.api.info(c[1], c[0])['response']
        return data

    def rename_chat(self, id, name):
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions;")
        c = cursor.fetchone()
        conn.close()
        data = self.api.rename_chat(c[1], c[0], name, id)
        return data

    def delete_chat(self, id):
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions;")
        c = cursor.fetchone()
        conn.close()
        data = self.api.delete_chat(c[1], c[0], id)
        return data

    def create_chat(self, name):
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions;")
        c = cursor.fetchone()
        conn.close()
        data = self.api.create_chat(c[1], c[0], name)
        return data