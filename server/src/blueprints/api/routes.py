import os
import threading

from flask import Blueprint, request, current_app
from app import db, SECRET_KEY, limiter
from .utils import gen_token, is_token_valid, gen_response, token_required, check_string, get_chat_as_dict
from models import User, Cluster, Chat, Message
from .settings import DEEPSEEK_API_KEY, SYSTEM_PROMPT_DEEPSEEK_MAKING, SYSTEM_PROMPT_DEEPSEEK_ANSWERING
from openai import OpenAI


bp = Blueprint('api', __name__)

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)


@bp.route('/auth', methods=['GET'])
@limiter.limit("1 per minute")
def get_auth_token():
    user_token, user_token_hash = gen_token(64, SECRET_KEY)
    cluster_token, cluster_token_hash = gen_token(64, SECRET_KEY)

    cluster = Cluster(token=cluster_token)
    db.session.add(cluster)
    db.session.flush()

    user = User(token=user_token_hash, cluster_id=cluster.id)
    db.session.add(user)
    db.session.commit()

    return gen_response({'user_token': user_token, 'user_id': user.id,
                         'cluster_token': cluster_token})


@bp.route('/info', methods=['POST'])
@limiter.limit("60 per minute")
@token_required
def get_info():
    user = request.user
    temp = {'user_id': user.id,
            'cluster_token': user.cluster.token,
            'chats': {},
            'users': []}

    for chat in user.cluster.chats:
        temp['chats'][str(chat.id)] = {'name': chat.name, 'ready': chat.ready, 'messages': []}
        for message in chat.messages:
            temp['chats'][str(chat.id)]['messages'].append({'user_sent': message.user_id, 'text': message.text, 'time': message.created_at})
    for user_i in user.cluster.users:
        temp['users'].append({'user_id': user_i.id, 'about': user_i.about})
    return gen_response(temp)


@bp.route('/join_cluster', methods=['POST'])
@limiter.limit("60 per minute")
@token_required
def join_cluster():
    user = request.user
    try:
        cluster_token = request.get_json()['cluster_token']
    except Exception:
        return gen_response({'comment': 'Invalid cluster token'}, status='ERROR', code=400)
    target = Cluster.query.filter_by(token=cluster_token).first()

    if not target:
        return gen_response({'comment': 'Invalid cluster token'}, status='ERROR', code=400)

    user.cluster_id = target.id
    db.session.commit()

    return gen_response()


@bp.route('/create_chat', methods=['POST'])
@limiter.limit("60 per minute")
@token_required
def create_chat():
    user = request.user
    try:
        name = request.get_json()['name']
    except Exception:
        return gen_response({'comment': 'No name given'}, status='ERROR', code=400)
    if not check_string(name):
        return gen_response({'comment': 'Invalid chat name'}, status='ERROR', code=400)

    chat = Chat(name=name, cluster_id=user.cluster_id)
    db.session.add(chat)
    db.session.commit()

    return gen_response()


@bp.route('/edit_chat_name', methods=['POST'])
@limiter.limit("60 per minute")
@token_required
def edit_chat_name():
    user = request.user
    try:
        name = request.get_json()['name']
        chat_id = request.get_json()['chat_id']
    except Exception:
        return gen_response({'comment': 'No name given'}, status='ERROR', code=400)
    if not check_string(name):
        return gen_response({'comment': 'Invalid chat name'}, status='ERROR', code=400)

    chat = Chat.query.get(chat_id)

    if not chat:
        return gen_response({'comment': 'Invalid chat id'}, status='ERROR', code=400)

    if chat.cluster_id != user.cluster_id:
        return gen_response({'comment': 'Access denied'}, status='ERROR', code=400)

    chat.name = name
    db.session.commit()

    return gen_response()


@bp.route('/delete_chat', methods=['POST'])
@limiter.limit("60 per minute")
@token_required
def delete_chat():
    user = request.user
    try:
        chat_id = request.get_json()['chat_id']
    except Exception:
        return gen_response({'comment': 'Got incomplete data'}, status='ERROR', code=400)

    chat = Chat.query.get(chat_id)

    if not chat:
        return gen_response({'comment': 'Invalid chat id'}, status='ERROR', code=400)

    if chat.cluster_id != user.cluster_id:
        return gen_response({'comment': 'Access denied'}, status='ERROR', code=400)

    db.session.delete(chat)
    db.session.commit()

    return gen_response()


@bp.route('/send_message', methods=['POST'])
@limiter.limit("60 per minute")
@token_required
def send_chat_message():
    user = request.user
    try:
        chat_id = request.get_json()['chat_id']
        text = request.get_json()['text']
    except Exception:
        return gen_response({'comment': 'Got incomplete data'}, status='ERROR', code=400)

    chat = Chat.query.get(chat_id)

    if not chat:
        return gen_response({'comment': 'Invalid chat id'}, status='ERROR', code=400)

    if chat.cluster_id != user.cluster_id or not chat.ready:
        return gen_response({'comment': 'Access denied'}, status='ERROR', code=400)

    if len(text) >= 5000 or len(text) == 0:
        return gen_response({'comment': 'The message is incorrect size'}, status='ERROR', code=400)

    msg = Message(text=text, chat_id=chat_id, user_id=user.id)
    chat.ready = False
    db.session.add(msg)
    db.session.commit()

    app_context = current_app.app_context()
    thread = threading.Thread(
        target=start_ai,
        args=(app_context, chat_id, msg.id, text)
    )
    thread.daemon = True
    thread.start()

    return gen_response()


def start_ai(app_context, chat_id, message_id, text):
    with app_context:
        try:
            from app import db
            from models import Message, Chat

            chat = Chat.query.get(chat_id)
            hist = [{"role": 'system', "content": SYSTEM_PROMPT_DEEPSEEK_ANSWERING}] + get_chat_as_dict(chat, max_messages=30)

            response = client.chat.completions.create(model="deepseek-chat", messages=hist, temperature=0.7, stream=False)

            ai_text = response.choices[0].message.content

            ai_msg = Message(text=ai_text, chat_id=chat_id, user_id=None)
            db.session.add(ai_msg)

            chat.ready = True
            db.session.commit()

        except Exception as e:
            chat = Chat.query.get(chat_id)
            chat.ready = True
            db.session.commit()