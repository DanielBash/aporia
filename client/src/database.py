import datetime
import os
import sqlite3
import threading
import time
import copy
from PyQt6.QtCore import QThread, pyqtSignal

from client.src import execute_agent


class ApiWorker(QThread):
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
                data = self.api(self.token, self.id)['response']
                if isinstance(data, list):
                    data = {'response': data}
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
        self.tasks_finished_ids = []

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
                self.add_row('sessions', {'user_id': data['user_id'], 'token': data['user_token'],
                                          'cluster_token': data['cluster_token']})
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

        self.update_thread = ApiWorker(self.api.info, c[0], c[1], interval=self.conf.feed_check_timeout)
        self.update_thread.dataReady.connect(self.update_info)
        self.update_thread.start()

        self.task_thread = ApiWorker(self.api.tasks, c[0], c[1], interval=self.conf.feed_check_timeout)
        self.task_thread.dataReady.connect(self.execute_info)
        self.task_thread.start()

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
        c = self.get_session()
        if 0 < len(name) < 100:
            self.info['chats'][id]['name'] = name
            self.info['chats'][id]['local'] = True
        data = self.api.rename_chat(c[1], c[0], name, id)
        return data

    def delete_chat(self, id):
        c = self.get_session()
        data = self.api.delete_chat(c[1], c[0], id)
        return data

    def create_chat(self, name):
        c = self.get_session()
        data = self.api.create_chat(c[1], c[0], name)
        return data

    def update_info(self, info):
        updated = copy.deepcopy(info)
        for i in self.info['chats'].keys():
            if i not in info['chats'].keys():
                continue
            if info['chats'][i]['name'] != self.info['chats'][i]['name']:
                if 'local' in self.info['chats'][i].keys():
                    updated['chats'][i] = self.info['chats'][i]
        for old_chat_id in self.info['chats'].keys():
            if old_chat_id not in updated['chats'].keys():
                continue
            old_messages = self.info['chats'][old_chat_id]['messages']
            new_messages = updated['chats'][old_chat_id]['messages']
            if len(old_messages) > len(new_messages):
                updated['chats'][old_chat_id]['messages'].append(old_messages[-1])
                updated['chats'][old_chat_id]['ready'] = False
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions LIMIT 1;")
        c = cursor.fetchone()
        session_id = c[0]
        cursor.execute(
            "UPDATE sessions SET cluster_token = ? WHERE rowid = ?;",
            (updated['cluster_token'], session_id)
        )
        conn.commit()
        conn.close()
        self.info = updated

    def send_message(self, text, id, force=False):
        c = self.get_session()
        if id not in self.info['chats']:
            if force:
                self.info['chats'][id] = {'messages': [], 'name': 'новый', 'ready': False}
                self.info['chats'][id]['messages'] = [{
                    "user_sent": c[0],
                    "text": text,
                    "time": datetime.datetime.now().isoformat(),
                    "local": True}]
                data = self.api.send_message(c[1], c[0], text, id)
                return data
            return
        self.info['chats'][id]['messages'].append({
            "user_sent": c[0],
            "text": text,
            "time": datetime.datetime.now().isoformat(),
            "local": True
        })
        self.info['chats'][id]['ready'] = False
        data = self.api.send_message(c[1], c[0], text, id)
        return data

    def execute_info(self, data):
        if not 'response' in data.keys():
            return
        data = [i for i in data['response'] if i['id'] not in self.tasks_finished_ids]
        if len(data) == 0:
            return
        thread = threading.Thread(
            target=self._execute_info,
            args=(data,),
            daemon=True
        )
        thread.start()

    def _execute_info(self, data):
        data = sorted(data, key=lambda x: x['timestamp'])
        self.tasks_finished_ids.append(data[0]['id'])
        c = self.get_session()
        ret = execute_agent.execute(data[0]['text'], self.conf)
        res = self.api.finish_task(c[1], c[0], ret, data[0]['id'])
        return res

    def send_new(self, text):
        new_id = self.create_chat('новый')['response']['id']
        self.send_message(text, new_id, force=True)
        return str(new_id)

    def get_cluster_token(self):
        return self.info['cluster_token']

    def get_session(self):
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions LIMIT 1;")
        c = cursor.fetchone()
        conn.close()
        return c

    def set_cluster_token(self, tok):
        c = self.get_session()
        self.api.join_cluster(c[1], c[0], tok)