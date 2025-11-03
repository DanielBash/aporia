import os
import threading
import time

from flask import Blueprint, request, current_app
from app import db, SECRET_KEY, limiter
from .utils import gen_token, is_token_valid, gen_response, token_required, check_string, get_chat_as_dict, \
    get_code_from_str, extract_code_metadata
from models import User, Cluster, Chat, Message, EventStack
from .settings import DEEPSEEK_API_KEY, SYSTEM_PROMPT_DEEPSEEK_MAKING, SYSTEM_PROMPT_DEEPSEEK_ANSWERING, \
    WAITING_FOR_RESPONSE_TIMEOUT, USER_OFFLINE_TIMEOUT
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
        text = f'[Сообщение отправлено с компьютера id:{user.id}]' + request.get_json()['text']
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

@bp.route('/get_tasks', methods=['POST'])
@limiter.limit("60 per minute")
@token_required
def get_events():
    user = request.user
    ans = []
    for i in user.events:
        if not i.finished:
            ans.append({'timestamp': i.created_at, 'text': i.text, 'id': i.id})
    return gen_response(ans)


@bp.route('/complete_event', methods=['POST'])
@limiter.limit("60 per minute")
@token_required
def complete_event():
    user = request.user
    try:
        rid = request.get_json()['event_id']
        text = request.get_json()['text']
        event = EventStack.query.get(rid)
    except:
        return gen_response({'comment': 'No event with given id'}, status='ERROR', code=400)

    if event.user.id != user.id:
        return gen_response({'comment': 'Access denied'}, status='ERROR', code=400)
    if len(text) > 5000:
        text = '... displaying last 4k symbols ...\n' + text[-4000:]

    event.return_text = text
    event.finished = True
    db.session.commit()

    return gen_response()


def start_ai(app_context, chat_id, message_id, text):
    with app_context:
        try:
            chat = Chat.query.get(chat_id)
            computers = Message.query.get(message_id).user.cluster.users
            user_id = Message.query.get(message_id).user.id

            comp_formated = []
            for i in computers:
                comp_formated.append(f'ID:{i.id}. Дополнительная информация: {i.about}')
            comp_formated = '\n'.join(comp_formated)

            prompt = SYSTEM_PROMPT_DEEPSEEK_MAKING + comp_formated

            hist = [{"role": 'system', "content": prompt}] + get_chat_as_dict(chat, max_messages=10)

            ans = ''

            while True:
                actual_hist = hist.copy()
                if ans != '':
                    actual_hist.append({"role": 'assistant', "content": ans})
                response = client.chat.completions.create(model="deepseek-chat", messages=actual_hist, temperature=0.7, stream=False)
                ai_text = response.choices[0].message.content
                ans += ai_text
                code = get_code_from_str(ai_text)
                code_filtered = extract_code_metadata(code, default_id=user_id)

                task_ids = []

                if len(code_filtered) == 0:
                    break

                for i in code_filtered:
                    task = EventStack(user_id=i[0], chat_id=chat_id, text=i[1])
                    db.session.add(task)
                    db.session.flush()
                    task_ids.append(task.id)
                    db.session.commit()

                start_time = time.time()
                while True:
                    elapsed = time.time() - start_time
                    if elapsed > WAITING_FOR_RESPONSE_TIMEOUT:
                        for i in task_ids:
                            task = EventStack.query.get(i)
                            task.return_text = 'Code didnt execute. It was elapsing too long.'
                            task.finished = True
                        db.session.commit()
                        break

                    any_task_unfinished = False
                    for i in task_ids:
                        db.session.expire_all()
                        task = EventStack.query.get(i)
                        if time.time() - task.user.last_online.timestamp() > USER_OFFLINE_TIMEOUT:
                            task.return_text = 'Code didnt execute. Target computer is offline.'
                            task.finished = True
                            db.session.commit()
                        if not task.finished:
                            any_task_unfinished = True

                    if not any_task_unfinished:
                        print('some tasks are not finished....')
                        break

                    time.sleep(1)
                for i in task_ids:
                    task = EventStack.query.get(i)
                    ans += f'Код для компьютера {task.user.id}. stdout: {task.return_text}\n'
                ans += 'Все? Если ты все закончил/узнал что надо, не выводи в следующем ответе код. Если можно улучшить результат, можно исполнить еще код.'
            hist = [{"role": 'system', "content": SYSTEM_PROMPT_DEEPSEEK_ANSWERING}] + hist[1:] + [{"role": 'assistant', "content": 'STARTED THINKING' + ans + 'ENDED THINKING'}]
            response = client.chat.completions.create(model="deepseek-chat", messages=hist, temperature=0.7, stream=False)
            ans = ans + '!THINKING!' + response.choices[0].message.content
            message = Message(chat_id=chat_id, text=ans)
            db.session.add(message)
            chat.ready = True
            db.session.commit()

        except Exception as e:
            chat = Chat.query.get(chat_id)
            chat.ready = True
            db.session.commit()