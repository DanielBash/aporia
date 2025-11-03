import os
import sqlite3
import time

from PyQt6.QtCore import QThread, pyqtSignal


class UpdateWorker(QThread):
    dataReady = pyqtSignal(dict)

    def __init__(self, api, id, token, parent=None, interval=1):
        super().__init__(parent)
        self.api = api
        self.running = True
        self.token = token
        self.id = id
        self.interval = interval

    def run(self):
        while self.running:
            try:
                data = self.api.info(self.token, self.id)['response']
                self.dataReady.emit(data)
            except Exception as e:
                print(e)
            time.sleep(self.interval)

    def stop(self):
        self.running = False


class Database:
    def __init__(self, conf):
        self.path = conf.paths.database_dir
        self.conf = conf
        self.api = conf.api

        self.info = {
            "user_id": 0,
            "cluster_token": "not-logged-in",
            "chats": {},
            "users": []}

        self.load()

    def load(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        conn = sqlite3.connect(str(self.path))
        cursor = conn.cursor()
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
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions LIMIT 1;")
        c = cursor.fetchone()
        conn.close()
        self.conf.api_auth = True
        self.update_thread = UpdateWorker(self.api, c[0], c[1], interval=self.conf.feed_check_timeout)
        self.update_thread.dataReady.connect(self.update_info)
        self.update_thread.start()

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
        return self.info

    def rename_chat(self, id, name):
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions LIMIT 1;")
        c = cursor.fetchone()
        conn.close()
        data = self.api.rename_chat(c[1], c[0], name, id)
        return data

    def delete_chat(self, id):
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions LIMIT 1;")
        c = cursor.fetchone()
        conn.close()
        data = self.api.delete_chat(c[1], c[0], id)
        return data

    def create_chat(self, name):
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions LIMIT 1;")
        c = cursor.fetchone()
        conn.close()
        data = self.api.create_chat(c[1], c[0], name)
        return data

    def update_info(self, info):
        self.info = info

    def send_message(self, text, id):
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions LIMIT 1;")
        c = cursor.fetchone()
        conn.close()
        data = self.api.send_message(c[1], c[0], text, id)
        return data