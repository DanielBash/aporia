import datetime
import secrets
import hashlib
import hmac
import time

from flask import jsonify
from functools import wraps
from models import User, Cluster, Message
from app import SECRET_KEY, db
from flask import request
import re


def gen_token(lenght=32, hmac_token='unsecure-token'):
    token = secrets.token_urlsafe(lenght)
    token_hash = hmac.new(hmac_token.encode('utf-8'), token.encode('utf-8'), hashlib.sha256).hexdigest()

    return token, token_hash

def is_token_valid(candidate, target, hmac_token='unsecure-token'):
    candidate = hmac.new(hmac_token.encode('utf-8'), candidate.encode('utf-8'), hashlib.sha256).hexdigest()

    return candidate == target

def gen_response(data=None, status='OK', code=200):
    if data is not None:
        data_final = {'status': status, 'response': data}
    else:
        data_final = {'status': status}
    return jsonify(data_final), code

def token_required(f):
    @wraps(f)
    def check_token(*args, **kwargs):
        data = request.get_json()

        if not data or 'user_token' not in data or 'user_id' not in data:
            return gen_response({'comment': 'Received incomplete data'}, status='ERROR', code=400)

        user = User.query.get(data['user_id'])

        if user is None or not is_token_valid(data['user_token'], user.token, SECRET_KEY):
            return gen_response({'comment': 'Invalid auth token'}, status='ERROR', code=400)
        request.user = user

        user.last_online = datetime.datetime.now()
        db.session.commit()

        return f(*args, **kwargs)
    return check_token

def check_string(s, max_length=100):
    if not s or not s.strip():
        return False

    if len(s) > max_length:
        return False

    if not re.match(r'^[\w\s\-]+$', s):
        return False

    return True

def get_chat_as_dict(chat, max_messages):
    messages = Message.query.filter_by(chat_id=chat.id).order_by(Message.created_at.asc()).limit(max_messages).all()

    conversation = []
    for message in messages:
        role = "assistant" if message.user_id is None else "user"
        conversation.append({
            "role": role,
            "content": message.text
        })
    return conversation

def get_code_from_str(string):
    oasis = string.split('```')
    return oasis[1::2]

def extract_code_metadata(code, default_id=1):
    code_filtered = []

    for i in range(len(code)):
        if code[i].startswith('python'):
            code[i] = code[i][6:]
            code[i] = code[i].lstrip('\n')

            lines = code[i].split('\n')
            if len(lines[0].split(':')) > 0 and 'ID' in lines[0].upper():
                try:
                    run_comp_id = int(lines[0].split(':')[1].rstrip())
                    code_filtered.append((run_comp_id, code[i]))
                except Exception:
                    code_filtered.append((default_id, code[i]))
    return code_filtered