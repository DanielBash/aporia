import os
from pathlib import Path
import requests


user_id = '%user_id'
user_token = '%user_token'
domain_name = '%domain_name'


def send_file(file):
    files = {
        'file': (Path(file.name).name, file, 'application/octet-stream')
    }

    json_data = {
        'user_id': user_id,
        'user_token': user_token
    }

    ret = requests.post(
        domain_name + '/send_file',
        data=json_data,
        files=files
    )

    return ret


def get_file(file):
    ret = requests.post(domain_name + '/get_file', json={'user_id': user_id, 'user_token': user_token, 'file': file})
    with open(file, 'wb') as f:
        f.write(ret.content)
        return f
