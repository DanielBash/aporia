import requests


class Api:
    def __init__(self, conf):
        self.conf = conf
        self.domain = conf.server_host

    def req(self, url, m='GET', d=None, h=None, t=5):
        m = m.upper()
        url = self.domain + '/' + url
        try:
            if m == "GET":
                response = requests.get(url, json=d, headers=h, timeout=t)
            else:
                response = requests.post(url, json=d, headers=h, timeout=t)
            return response.json()
        except Exception as e:
            return {}

    def auth(self):
        return self.req('auth')

    def info(self, token, id):
        return self.req('info', m='post', d={'user_token': token, 'user_id': id})

    def create_chat(self, token, id, name):
        return self.req('create_chat', m='post', d={'user_token': token, 'user_id': id, 'name': name})

    def rename_chat(self, token, id, name, chat_id):
        return self.req('edit_chat_name', m='post', d={'user_token': token, 'user_id': id, 'name': name, 'chat_id': chat_id})

    def delete_chat(self, token, id, chat_id):
        return self.req('delete_chat', m='post', d={'user_token': token, 'user_id': id, 'chat_id': chat_id})

    def send_message(self, token, id, text, chat_id):
        return self.req('send_message', m='post', d={'user_token': token, 'user_id': id, 'chat_id': chat_id, 'text': text})

    def tasks(self, token, id):
        return self.req('get_tasks', m='post', d={'user_token': token, 'user_id': id})
    def finish_task(self, token, id, text, event_id):
        return self.req('complete_task', m='post', d={'user_token': token, 'user_id': id, 'text': text, 'event_id': event_id})