import os
from flask import Blueprint, render_template, send_file
from models import User, Cluster, Chat, Message, EventStack
from app import db


current_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(current_dir, 'templates')

bp = Blueprint('main', __name__, template_folder=template_dir)


@bp.route('/')
def docs_welcome():
    users_count = User.query.count()
    messages_count = Message.query.count()
    code_executions = EventStack.query.count()
    return render_template('markdown-view.html', contents='WELCOME', title='Апория: Главная',
                           users_count=users_count, messages_count=messages_count, code_executions=code_executions)

@bp.route('/api')
def docs_api():
    users_count = User.query.count()
    messages_count = Message.query.count()
    code_executions = EventStack.query.count()
    return render_template('markdown-view.html', contents='API', title='Апория: API',
                           users_count=users_count, messages_count=messages_count, code_executions=code_executions)

@bp.route('/download')
def download_client():
    return send_file('blueprints/main/downloads/aporia.exe', as_attachment=True)