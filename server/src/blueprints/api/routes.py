import os
import threading
import time
from pathlib import Path

from flask import Blueprint, request, current_app, jsonify
from app import db, SECRET_KEY, limiter
from .utils import gen_token, is_token_valid, gen_response, token_required, check_string, get_chat_as_dict, \
    get_code_from_str, extract_code_metadata
from models import User, Cluster, Chat, Message, EventStack
from .settings import DEEPSEEK_API_KEY, SYSTEM_PROMPT_DEEPSEEK_MAKING, SYSTEM_PROMPT_DEEPSEEK_ANSWERING, \
    WAITING_FOR_RESPONSE_TIMEOUT, USER_OFFLINE_TIMEOUT, MAX_FILE_SIZE, UPLOAD_FOLDER
from openai import OpenAI
from werkzeug.utils import secure_filename
from flask import send_file

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
            temp['chats'][str(chat.id)]['messages'].append(
                {'user_sent': message.user_id, 'text': message.text, 'time': message.created_at})
    for user_i in user.cluster.users:
        temp['users'].append(
            {'user_id': user_i.id, 'about': user_i.about, 'last_online': time.time() - user_i.last_online.timestamp()})
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


@bp.route('/set_about', methods=['POST'])
@limiter.limit("60 per minute")
@token_required
def set_about():
    user = request.user
    try:
        about_text = request.get_json()['text']
    except Exception:
        return gen_response({'comment': 'Invalid cluster token'}, status='ERROR', code=400)
    if len(about_text) <= 500:
        user.about = about_text
        db.session.commit()
    else:
        return gen_response({'comment': 'Text is too big'}, status='ERROR', code=400)

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

    return gen_response({'id': chat.id})


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


@bp.route('/complete_task', methods=['POST'])
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
        gen_ai(app_context, chat_id, message_id, text)


def gen_ai(app_context, chat_id, message_id, text):
    chat = Chat.query.get(chat_id)
    computers = Message.query.get(message_id).user.cluster.users
    user_id = Message.query.get(message_id).user.id

    # Create thinking system prompt
    computer_info = '\n'.join([f'ID: {i.id}. Дополнительная информация: {i.about}' for i in computers])
    thinking_prompt = SYSTEM_PROMPT_DEEPSEEK_MAKING + '\n' + computer_info
    context_history = [{"role": 'system', "content": thinking_prompt}] + get_chat_as_dict(chat, max_messages=10)

    max_iterations = 5
    current_iteration = 0

    thinking_generated = ''
    while max_iterations > current_iteration:
        current_iteration += 1

        print(f'Iteration {current_iteration} started.')

        # Creating dynamic system prompt
        dynamic_history = context_history.copy()
        if thinking_generated != '':
            dynamic_history.append({"role": 'assistant', "content": thinking_generated})

        # Getting response
        response = client.chat.completions.create(model="deepseek-chat", messages=dynamic_history, temperature=0.7, stream=False)
        iteration_generated = response.choices[0].message.content
        thinking_generated += '\n' + iteration_generated

        # Extracting code
        code = get_code_from_str(iteration_generated)
        code_filtered = extract_code_metadata(code, default_id=user_id)

        tasks = []

        if len(code_filtered) == 0:
            break

        for i in code_filtered:
            task = EventStack(user_id=i[0], chat_id=chat_id, text=i[1])
            db.session.add(task)
            tasks.append(task)

            db.session.commit()

        print(f'Code extracted {len(tasks)} code tasks')

        start_time = time.time()
        while True:
            db.session.expire_all()

            elapsed = time.time() - start_time
            if elapsed > WAITING_FOR_RESPONSE_TIMEOUT:
                for task in tasks:
                    task.return_text = 'Code was elapsing for too long.'
                    task.finished = True
                db.session.commit()
                break


            tasks_finished = True
            for task in tasks:
                if time.time() - task.user.last_online.timestamp() > USER_OFFLINE_TIMEOUT:
                    task.return_text = 'Target computer was offline.'
                    task.finished = True
                    db.session.commit()
                if not task.finished:
                    tasks_finished = False

            if tasks_finished:
                print('every task is finished....')
                break

            time.sleep(1)

        thinking_generated += '\n Вот результаты работы:\n'

        for task in tasks:
            thinking_generated += f'КОМПЬЮТЕР: {task.user.id}. ВЫВОД: {task.return_text}\n'
        thinking_generated += '\nВсе? Если тебе больше нечего делать, не выводи код'

    # Generating answer
    answer_history = ([{"role": 'system', "content": SYSTEM_PROMPT_DEEPSEEK_ANSWERING}] + context_history[1:] +
                      [{"role": 'assistant', "content": 'STARTED THINKING' + thinking_generated + 'ENDED THINKING'}])
    response = client.chat.completions.create(model="deepseek-chat", messages=answer_history, temperature=1.5, stream=False)
    thinking_generated = thinking_generated + '!THINKING!' + response.choices[0].message.content

    print(f'Final result: {thinking_generated}')

    message = Message(chat_id=chat_id, text=thinking_generated)
    db.session.add(message)
    chat.ready = True
    db.session.commit()

@bp.route('/send_file', methods=['POST'])
@limiter.limit("60 per minute")
def send_storage_file():
    data = request.form

    if not data or 'user_token' not in data or 'user_id' not in data:
        return gen_response({'comment': 'Received incomplete data'}, status='ERROR', code=400)

    user = User.query.get(data['user_id'])

    if user is None or not is_token_valid(data['user_token'], user.token, SECRET_KEY):
        return gen_response({'comment': 'Invalid auth token'}, status='ERROR', code=400)

    token = str(user.cluster.token)

    if 'file' not in request.files:
        return gen_response({'comment': 'No file selected'}, status='ERROR', code=400)

    file = request.files['file']
    if file.filename == '':
        return gen_response({'comment': 'The filename isnt correct'}, status='ERROR', code=400)
    filename = secure_filename(file.filename)

    file_size = request.content_length
    if file_size is None:
        pass
    elif file_size > MAX_FILE_SIZE:
        return gen_response({'comment': 'File exceeds file limit'}, status='ERROR', code=400)

    os.makedirs(str(UPLOAD_FOLDER / token), exist_ok=True)
    file_path = os.path.join(str(UPLOAD_FOLDER / token), filename)
    try:
        file.save(file_path)

        return jsonify({
            'message': 'File uploaded successfully',
            'filename': filename,
            'size': file_size,
            'user_id': user.id
        }), 200

    except Exception:
        return jsonify({'error': f'Failed to save file'}), 500


@bp.route('/get_file', methods=['POST'])
@limiter.limit("60 per minute")
def get_storage_file():
    data = request.get_json()

    required_fields = ['user_token', 'user_id', 'file']
    if not data or any(field not in data for field in required_fields):
        return gen_response({'comment': 'Received incomplete data'}, status='ERROR', code=400)

    user = User.query.get(data['user_id'])

    if user is None or not is_token_valid(data['user_token'], user.token, SECRET_KEY):
        return gen_response({'comment': 'Invalid auth token'}, status='ERROR', code=400)

    token = str(user.cluster.token)
    filename = secure_filename(data['file'])

    if not filename:
        return gen_response({'comment': 'Invalid filename'}, status='ERROR', code=400)

    file_path = Path(str(os.path.join(str(UPLOAD_FOLDER / token), filename)))

    if not file_path.exists() or not file_path.is_file():
        return gen_response({'comment': 'File not found'}, status='ERROR', code=404)
    file_size = file_path.stat().st_size
    if file_size > MAX_FILE_SIZE:
        return gen_response({'comment': 'File too large'}, status='ERROR', code=400)

    try:
        file_ext = file_path.suffix.lower()
        mimetype = None

        if file_ext in ['.txt', '.py', '.js', '.css', '.html']:
            mimetype = f'text/{file_ext[1:]}' if file_ext != '.txt' else 'text/plain'
        elif file_ext in ['.jpg', '.jpeg']:
            mimetype = 'image/jpeg'
        elif file_ext == '.png':
            mimetype = 'image/png'
        elif file_ext == '.pdf':
            mimetype = 'application/pdf'

        return send_file(
            str(file_path),
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype,
            conditional=True
        )
    except Exception as e:
        return gen_response({'comment': f'Error retrieving file {e}'}, status='ERROR', code=500)
