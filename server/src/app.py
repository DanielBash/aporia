from flask import Flask
from models import db, limiter
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


SECRET_KEY = 'iAnA_1VKb6qTLMnIsYut1fmr97qzmnAyIm6Se9BxCikBTHuh7BWWXgwBxIZF4T8HMoYuWxD7vQSBaqbzB7n0wQ'

def create_app():
    global limiter
    app = Flask(__name__)

    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = SECRET_KEY

    db.init_app(app)
    limiter.init_app(app)

    with app.app_context():
        from blueprints.main.routes import bp as main_bp
        from blueprints.api.routes import bp as api_bp

        app.register_blueprint(main_bp)
        app.register_blueprint(api_bp, url_prefix="/api")

        db.create_all()
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=80)
