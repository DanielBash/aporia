import os
import requests


user_id = '%user_id'
user_token = '%user_token'
domain_name = '%domain_name'


def send_file(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} not found")

    file_size = os.path.getsize(file_path)
    if file_size > 100 * 1024 * 1024:
        raise ValueError(f"File size {file_size} exceeds 100MB limit")

    with open(file_path, 'rb') as file:
        files = {
            'file': (os.path.basename(file_path), file, 'application/octet-stream')
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
    return ret