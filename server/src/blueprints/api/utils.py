import secrets
import hashlib
import hmac
from flask import jsonify
from functools import wraps
from models import User, Cluster, Message
from app import SECRET_KEY
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