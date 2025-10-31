from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
db = SQLAlchemy()

class Timestamp:
    created_at = db.Column(db.DateTime, default=func.now(), nullable=False)


class Cluster(db.Model, Timestamp):
    __tablename__ = 'clusters'
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(256), unique=True, nullable=False)

    users = db.relationship('User', back_populates='cluster')
    chats = db.relationship('Chat', back_populates='cluster')


class User(db.Model, Timestamp):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(256), unique=True, nullable=False)

    about = db.Column(db.String(500))

    cluster_id = db.Column(db.Integer, db.ForeignKey('clusters.id'))
    cluster = db.relationship('Cluster', back_populates='users')

    last_online = db.Column(db.DateTime, default=func.now(), nullable=False)

    messages = db.relationship('Message', back_populates='user')

    events = db.relationship('EventStack', back_populates='user')


class Chat(db.Model, Timestamp):
    __tablename__ = 'chats'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False)

    cluster_id = db.Column(db.Integer, db.ForeignKey('clusters.id'))
    cluster = db.relationship('Cluster', back_populates='chats')

    messages = db.relationship('Message', back_populates='chat', cascade='all, delete-orphan',
                               passive_deletes=True)

    ready = db.Column(db.Boolean, unique=False, default=True)

    events = db.relationship('EventStack', back_populates='chat', cascade='all, delete-orphan',
                               passive_deletes=True)


class Message(db.Model, Timestamp):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    chat_id = db.Column(db.Integer, db.ForeignKey('chats.id', ondelete='CASCADE'), nullable=False)
    chat = db.relationship('Chat', back_populates='messages')

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user = db.relationship('User', back_populates='messages')


class EventStack(db.Model, Timestamp):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user = db.relationship('User', back_populates='events')

    chat_id = db.Column(db.Integer, db.ForeignKey('chats.id', ondelete='CASCADE'), nullable=False)
    chat = db.relationship('Chat', back_populates='events')

    finished = db.Column(db.Boolean, unique=False, default=False)
    return_text = db.Column(db.Text)