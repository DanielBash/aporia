import datetime
import os
import sqlite3
import threading
import time
import copy
from PyQt6.QtCore import QThread, pyqtSignal
from client.src import execute_agent
import random


# API ASINC LISTENER
class ApiWorker(QThread):
    pulled = pyqtSignal(dict)

    def __init__(self, api_function, user_id, token, interval=1):
        super().__init__(None)

        self.api_function = api_function
        self.running = True
        self.token = token
        self.id = user_id
        self.interval = interval

    def run(self):
        while self.running:
            data = self.api_function(self.token, self.id)
            self.pulled.emit({'data': data})
            time.sleep(self.interval)

    def stop(self):
        self.running = False


# DATABASE FOR ASYNC DATA MANAGEMENT AND INSTANT SERVING
class Database:
    def __init__(self, conf):
        self.conf = conf

        self.session_data = {
            "user_id": 0,
            "user_token": "not-logged-in",
            "cluster_token": "not-logged-in",
            "about": "None"
        }
        self.settings = conf.default_settings
        self.chats = []
        self.tasks = []
        self.users = []

        self.tasks_finished = set()
        self.deleted_chats = set()

        self.update_thread = None
        self.task_thread = None

        self._start_app_session()

    # -- general sqlite functions
    def _add_row(self, table, data):
        columns = data.keys()
        columns_str = '(' + ', '.join(['?'] * len(columns)) + ')'
        vals = tuple(data.values())

        conn, cursor = self._database_session()
        cursor.execute(f"INSERT INTO {table} ({', '.join(columns)}) VALUES {columns_str}", vals)
        conn.commit()
        conn.close()

    def _update_row(self, table, data, where_clause=""):
        set_clause = ', '.join([f"{key} = ?" for key in data.keys()])
        vals = tuple(data.values())

        conn, cursor = self._database_session()
        query = f"UPDATE {table} SET {set_clause}"
        if where_clause:
            query += f" WHERE {where_clause}"
        cursor.execute(query, vals)
        conn.commit()
        conn.close()

    def _clear_table(self, name):
        conn, cursor = self._database_session()
        cursor.execute(f"DELETE FROM {name};")

        conn.commit()
        conn.close()

    def _database_session(self):
        connection = sqlite3.connect(str(self.conf.paths.database_dir))
        cursor = connection.cursor()
        return connection, cursor

    # -- database management
    def _create_database(self):
        os.makedirs(os.path.dirname(self.conf.paths.database_dir), exist_ok=True)

        conn, cursor = self._database_session()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS data (
        user_id INTEGER,
        user_token TEXT,
        cluster_token TEXT,
        about TEXT,
        current_theme TEXT,
        keyboard_shortcut TEXT,
        notifications BOOLEAN);
        """)

        conn.commit()
        conn.close()

    def _save_session(self):
        db_data = {
            'user_id': self.session_data['user_id'],
            'user_token': self.session_data['user_token'],
            'cluster_token': self.session_data['cluster_token'],
            'about': self.session_data['about'],
            'current_theme': self.settings.get('current_theme', 'default'),
            'keyboard_shortcut': self.settings.get('open_window_shortcut', ''),
            'notifications': 1 if self.settings.get('notifications', True) else 0
        }

        if self._previous_session_saved():
            self._update_row('data', db_data, f"user_id = {self.session_data['user_id']}")
        else:
            self._add_row('data', db_data)

    def _previous_session_saved(self):
        conn, cursor = self._database_session()
        cursor.execute("SELECT COUNT(*) FROM data;")
        c = cursor.fetchone()[0]
        conn.close()
        return c > 0

    def _create_session(self):
        self._create_database()
        data = self.conf.api.auth()['response']

        self.session_data['user_token'] = data['user_token']
        self.session_data['user_id'] = data['user_id']
        self.session_data['cluster_token'] = data['cluster_token']

        self._save_session()

    def _load_session(self):
        conn, cursor = self._database_session()
        cursor.execute("SELECT * FROM data LIMIT 1;")

        data = cursor.fetchone()
        conn.close()

        self.session_data['user_id'] = data[0]
        self.session_data['user_token'] = data[1]
        self.session_data['cluster_token'] = data[2]
        self.session_data['about'] = data[3]

        self.settings['current_theme'] = data[4]
        self.settings['open_window_shortcut'] = data[5]
        self.settings['notifications'] = bool(data[6])

    def _start_app_session(self):
        if not os.path.exists(str(self.conf.paths.database_dir)) or not self._previous_session_saved():
            self._create_session()
            self.conf.notification_manager.show_notification(title='Апория', text='Создан новый пользователь')
        else:
            self._load_session()

        self.conf.api_auth = True

        self._start_update_workers()

    def _start_update_workers(self):
        self.update_thread = ApiWorker(self.conf.api.info, self.session_data['user_id'],
                                       self.session_data['user_token'], interval=self.conf.server_pull_interval)
        self.update_thread.pulled.connect(self._update_data)
        self.update_thread.start()

        self.task_thread = ApiWorker(self.conf.api.tasks, self.session_data['user_id'], self.session_data['user_token'],
                                     interval=self.conf.server_pull_interval)
        self.task_thread.pulled.connect(self.execute_relevant_task)
        self.task_thread.start()

    # -- quick data access
    def _get_chat_index_by(self, local_id=None, public_id=None):
        for i in range(len(self.chats)):
            if self.chats[i]['local_id'] == local_id:
                return i
            elif self.chats[i]['public_id'] == public_id:
                return i
        return None

    def _it(self):
        return self.session_data['user_token'], self.session_data['user_id']

    # -- data serving and quick actions
    def get_all(self):
        ret = {}
        ret.update(self.settings)
        ret.update(self.session_data)
        ret['chats'] = self.chats
        ret['users'] = self.users
        ret['tasks'] = self.tasks

        return ret

    def rename_chat(self, local_id, name):
        chat_index = self._get_chat_index_by(local_id=local_id)
        self.chats[chat_index]['name'] = name

        threading.Thread(target=self._rename_chat_api, args=(local_id, name), daemon=True).start()

    def _rename_chat_api(self, local_id, name):
        while self.chats[self._get_chat_index_by(local_id=local_id)]['public_id'] == 0:
            pass
        chat = self.chats[self._get_chat_index_by(local_id=local_id)]
        self.conf.api.rename_chat(*self._it(), name, chat['public_id'])

    def delete_chat(self, local_id):
        threading.Thread(target=self._delete_chat_api, args=(local_id,), daemon=True).start()

    def _delete_chat_api(self, local_id):
        while self.chats[self._get_chat_index_by(local_id=local_id)]['public_id'] == 0:
            pass
        chat = self.chats[self._get_chat_index_by(local_id=local_id)].copy()
        self.deleted_chats.add(chat['public_id'])
        del self.chats[self._get_chat_index_by(local_id=local_id)]
        self.conf.api.delete_chat(*self._it(), chat['public_id'])

    def create_chat(self, name):
        local_id = random.randint(-10 ** 10, -1)
        self.chats.append({'local_id': local_id,
                           'public_id': 0,
                           'ready': True,
                           'name': name,
                           'messages': []})

        threading.Thread(target=self._create_chat_api, args=(local_id, name), daemon=True).start()

        return local_id

    def _create_chat_api(self, local_id, name):
        self.chats[self._get_chat_index_by(local_id=local_id)]['public_id'] = self.conf.api.create_chat(*self._it(), name=name)['response']['id']

    def send_message(self, text, local_id):
        chat_index = self._get_chat_index_by(local_id=local_id)

        if chat_index is None:
            local_id = self.create_chat(self.conf.default_chat_name)
            chat_index = self._get_chat_index_by(local_id=local_id)

        self.chats[chat_index]['messages'].append({'timestamp': datetime.datetime.now(), 'text': '[Отправлено с компа]' + text, 'user_sent': self.session_data['user_id']})
        self.chats[chat_index]['ready'] = False

        threading.Thread(target=self._send_message_api, args=(local_id, text), daemon=True).start()

        return local_id

    def _send_message_api(self, local_id, text):
        while self.chats[self._get_chat_index_by(local_id=local_id)]['public_id'] == 0:
            pass
        chat = self.chats[self._get_chat_index_by(local_id=local_id)]
        self.conf.api.send_message(*self._it(), text, chat['public_id'])

    def set_cluster_token(self, token):
        threading.Thread(target=self._set_cluster_token, args=(token,), daemon=True).start()

    def _set_cluster_token(self, token):
        self.conf.api.join_cluster(*self._it(), token)

    def _update_data(self, data):
        if 'response' not in data['data'].keys():
            return

        data = data['data']['response']
        all_local_public_ids = set()
        received_all_indexes = True

        # update cluster token
        self.session_data['cluster_token'] = data['cluster_token']

        # handle chat delete
        delete_schedule = set()
        for i in range(len(self.chats)):
            if self.chats[i]['public_id'] != 0 and self.chats[i]['public_id'] not in data['chats'].keys():
                delete_schedule.add(i)
            else:
                all_local_public_ids.add(self.chats[i]['public_id'])
                if self.chats[i]['public_id'] == 0:
                    received_all_indexes = False

        for i in delete_schedule:
            del self.chats[i]

        # handle chat addition
        for i in data['chats'].keys():
            if i not in all_local_public_ids and i not in self.deleted_chats and received_all_indexes:
                self.chats.append(data['chats'][i] | {'public_id': i, 'local_id': random.randint(-10 ** 10, -1)})

        # handle message pull
        for i in range(len(self.chats)):
            if self.chats[i]['public_id'] not in data['chats'].keys():
                continue
            if len(self.chats[i]['messages']) < len(data['chats'][self.chats[i]['public_id']]['messages']):
                self.chats[i]['messages'] = data['chats'][self.chats[i]['public_id']]['messages']

        # handle ready check
        for i in range(len(self.chats)):
            if self.chats[i]['public_id'] not in data['chats'].keys():
                continue
            self.chats[i]['ready'] = data['chats'][self.chats[i]['public_id']]['ready']

    # -- script execution manager
    def execute_relevant_task(self, data):
        if not 'response' in data['data'].keys():
            return
        data = [i for i in data['data']['response'] if i['id'] not in self.tasks_finished]
        if len(data) == 0:
            return
        threading.Thread(
            target=self._execute_task,
            args=(data,),
            daemon=True
        ).start()

    def _execute_task(self, data):
        data = sorted(data, key=lambda x: x['timestamp'])
        self.tasks_finished.add(data[0]['id'])
        ret = execute_agent.execute(data[0]['text'], self.conf)
        res = self.conf.api.finish_task(*self._it(), ret, data[0]['id'])
        return res