import os
from flask import Blueprint, render_template, send_file


current_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(current_dir, 'templates')

bp = Blueprint('main', __name__, template_folder=template_dir)


@bp.route('/')
def docs_welcome():
    return render_template('markdown-view.html', contents='WELCOME', title='Апория: Главная')

@bp.route('/api')
def docs_api():
    return render_template('markdown-view.html', contents='API', title='Апория: API')

@bp.route('/download')
def download_client():
    return send_file('blueprints/main/downloads/aporia.exe', as_attachment=True)