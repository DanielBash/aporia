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
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(e)
            return {}

    def auth(self):
        return self.req('auth')

    def info(self, token, id):
        return self.req('info', m='post', d={'user_token': token, 'user_id': id})
