import mdtex2html
import os
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--enable-gpu-rasterization --ignore-gpu-blocklist"
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (QMainWindow, QPushButton,
                             QLineEdit, QListWidget, QListWidgetItem, QLabel,
                             QAbstractItemView, QMenu, QDialog, QFrame)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QUrl, QPoint
from PyQt6.QtGui import QIcon, QAction, QColor
from PyQt6.QtCore import QTimer
from ..components.prompt_edit import PromptEdit
from ..windows.input_popup import TextReq
from ..windows.settings_popup import SettingsPrompt
from jinja2 import Template
import html as cgi
from copy import deepcopy

# DATABASE SYNC
class DatabaseWorker(QThread):
    changed = pyqtSignal(dict)

    def __init__(self, db):
        super().__init__(None)

        self.db = db
        self.prev_data = {}

        self.running = True

    def run(self):
        while self.running:
            data = self.db.get_all()
            if str(data) != str(self.prev_data):
                self.changed.emit(data)
                self.prev_data = deepcopy(data)
            QThread.msleep(100)

    def stop(self):
        self.running = False


# MAIN WINDOW, DISPLAYING NECESSARY STUFF
class MainWindow(QMainWindow):
    def __init__(self, config, pos=(0, 0)):
        super().__init__()

        self.conf = config

        self.menu_opened = True
        self.needs_destroy = False

        self.prompt = None
        self.gen_btn = None
        self.menu_btn = None
        self.message_bar = None
        self.search = None
        self.add_chat_btn = None
        self.settings_btn = None
        self.chats_bar = None
        self.no_chats_label = None
        self.messages_border = None
        self.no_messages_label = None

        self.data = None

        self.chat_selected = None
        self.chats_displayed = []

        self.messages_displayed = []

        self.current_theme = None

        self.database_worker = None

        self.dragging = False
        self.drag_position = QPoint()

        self.setupWindow(pos)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.MiddleButton and self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.dragging = False
            event.accept()

    def setupWindow(self, pos):
        self.setWindowTitle(f'{self.conf.assistant_name}')
        self.setFixedSize(self.conf.tile * 13, self.conf.tile * 9)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.move(int(pos[0] - self.conf.tile * 8.5), int(pos[1] - self.conf.tile * 8.5))
        self.setWindowIcon(QIcon(self.conf.paths.icon("icon_active")))

        self._update_theme()
        self.setupUi()
        self.toggle_menu()
        self.setup_workers()

    def setup_workers(self):
        self.database_worker = DatabaseWorker(self.conf.db)
        self.database_worker.changed.connect(self.update_data)
        self.database_worker.start()

    def setupUi(self):
        t = self.conf.tile

        # МЕНЮ ОТКРЫТЬ: КНОПКА
        self.menu_btn = QPushButton(self)

        self.menu_btn.setFixedSize(t, t)
        self.menu_btn.move(t * 4, t * 8)

        self.menu_btn.setToolTip('Все чаты')
        self.menu_btn.setIcon(QIcon(self.conf.paths.icon("menu_btn")))
        self.menu_btn.setIconSize(QSize(int(t * 0.7), int(t * 0.7)))
        self.menu_btn.clicked.connect(self.toggle_menu)

        # ГЕНЕРАЦИЯ: КНОПКА
        self.gen_btn = QPushButton(self)

        self.gen_btn.setFixedSize(t, t)
        self.gen_btn.move(t * 12, t * 8)

        self.gen_btn.setToolTip('Отправить команду')
        self.gen_btn.setIcon(QIcon(self.conf.paths.icon("generate_btn_active")))
        self.gen_btn.setIconSize(QSize(int(t * 0.7), int(t * 0.7)))
        self.gen_btn.clicked.connect(self.send_message)

        # ДОБАВИТЬ ЧАТ: КНОПКА
        self.add_chat_btn = QPushButton(self)

        self.add_chat_btn.setFixedSize(t * 4, t)
        self.add_chat_btn.move(0, t * 8)

        self.add_chat_btn.setToolTip('Добавить чат')
        self.add_chat_btn.setIcon(QIcon(self.conf.paths.icon("add_chat_btn_active")))
        self.add_chat_btn.setIconSize(QSize(int(t * 0.7), int(t * 0.7)))

        self.add_chat_btn.clicked.connect(self.add_chat)

        # ДОСТУПНЫЕ ЧАТЫ
        self.chats_bar = QListWidget(self)
        self.chats_bar.setFixedSize(t * 4, t * 7 - 2)
        self.chats_bar.move(0, t + 1)
        self.chats_bar.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chats_bar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chats_bar.itemSelectionChanged.connect(self.select_chat)
        self.chats_bar.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.chats_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.chats_bar.customContextMenuRequested.connect(self.chat_item_dropdown)

        # ЗКАРЫТЬ: КНОПКА
        self.settings_btn = QPushButton(self)

        self.settings_btn.setFixedSize(t, t)
        self.settings_btn.move(0, 0)

        self.settings_btn.setToolTip('Настройки')
        self.settings_btn.setIcon(QIcon(self.conf.paths.icon("close_btn_active")))
        self.settings_btn.setIconSize(QSize(int(t * 0.7), int(t * 0.7)))
        self.settings_btn.clicked.connect(self.settings)

        # ПОИСК: ПОЛЕ ВВОДА
        self.search = QLineEdit(self)

        self.search.setFixedSize(t * 3, t)
        self.search.move(t, 0)

        self.search.setPlaceholderText(f"🔍 Поиск")
        self.search.textChanged.connect(self.update_data)

        # ТЕКУЩИЙ ЧАТ: ПОЛЕ
        self.messages_border = QFrame(self)
        self.messages_border.setObjectName('ContentBlock')
        self.messages_border.setFixedSize(t * 9, t * 8 - 1)
        self.messages_border.move(t * 4 + 1, 0)
        self.messages_border.hide()
        self.message_bar = QWebEngineView(self)
        self.message_bar.setFixedSize(t * 8, t * 7 - 1)
        self.message_bar.move(int(t * 4.5 + 1), int(t * 0.5))
        self.message_bar.hide()
        self.message_bar.page().setBackgroundColor(QColor(0, 0, 0, 0))
        self.message_bar.setHtml('')

        settings = self.message_bar.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, False)

        # ПОДСКАЗКА: НЕТ ЧАТОВ
        self.no_chats_label = QLabel(self)
        self.no_chats_label.move(int(t * 1), int(t * 4))
        self.no_chats_label.setText('Нет чатов...')

        # ПОДСКАЗКА: НЕТ СООБЩЕНИЙ
        self.no_messages_label = QLabel(self)
        self.no_messages_label.move(int(t * 6.8), int(t * 4))
        self.no_messages_label.setFixedSize(t * 5, t * 1)
        self.no_messages_label.setText('Нет сообщений...')

        # ЗАПРОС: ПОЛЕ ВВОДА
        self.prompt = PromptEdit(self)

        self.prompt.setFixedSize(t * 7, t)
        self.prompt.move(t * 5, t * 8)

        self.prompt.setPlaceholderText(f"{self.conf.assistant_name} ждет команды...")
        self.prompt.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.prompt.textChanged.connect(self._prompt_edited)
        self.prompt.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.prompt.returnPressed.connect(self.send_message)

        self.prompt.textChanged.connect(self._prompt_edited)
        QTimer.singleShot(100, self.prompt.setFocus)

        if not self.conf.api_auth:
            self.conf.notification_manager.show_notification(title='Апория', text='Авторизация не завершена')
            self.close_window()

    def toggle_menu(self):
        if self.menu_opened:
            self.menu_btn.setIcon(QIcon(self.conf.paths.icon("menu_btn")))
            self.settings_btn.hide()
            self.search.hide()
            self.chats_bar.hide()
            self.add_chat_btn.hide()
        else:
            self.menu_btn.setIcon(QIcon(self.conf.paths.icon("active_menu_btn")))
            self.settings_btn.show()
            self.search.show()
            self.chats_bar.show()
            self.add_chat_btn.show()
        self.menu_opened = not self.menu_opened

    def _update_theme(self):
        if self.current_theme != self.conf.db.settings['current_theme']:
            self.current_theme = self.conf.db.settings['current_theme']
            self.setStyleSheet(self.conf.paths.style(self.current_theme))

    def _prompt_edited(self):
        t = self.conf.tile
        self.changed = True
        h = self.prompt.document().size().height()
        h = max(min(int(h) + 5, 120), t)
        if h != self.prompt.height():
            self.prompt.setFixedHeight(h)
        self.prompt.move(t * 5, t * 8 + 40 - h)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close_window()

    def close_window(self):
        self.needs_destroy = True
        self.deleteLater()

    def update_data(self):
        if not self.conf.api_auth:
            return
        self.data = self.conf.db.get_all()

        self._update_chats_bar()
        self._update_message_bar()
        self._update_theme()
        self._update_visibility()

    def _update_chats_bar(self):
        display_chats = []
        search_req = self.search.text()

        for i in self.data['chats']:
            if search_req.lower() in i['name'].lower():
                display_chats.append(i)

        display_chats = sorted(display_chats, key=lambda x: x['local_id'])
        if str(display_chats) == str(self.chats_displayed):
            return
        else:
            self.chats_displayed = deepcopy(display_chats)

        self.chats_bar.clear()
        for i in self.chats_displayed:
            item = QListWidgetItem(i['name'])
            item.setData(50, i['local_id'])
            self.chats_bar.addItem(item)
            if i['local_id'] == self.chat_selected:
                self.chats_bar.setCurrentItem(item)

    def select_chat(self):
        selected_items = self.chats_bar.selectedItems()

        if selected_items:
            item = selected_items[0]
            self.chat_selected = item.data(50)
        else:
            pass

        self.update_data()

    def chat_item_dropdown(self, pos):
        item = self.chats_bar.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)

        del_action = QAction('Удалить чат', self)
        rename_action = QAction('Переименовать', self)

        del_action.triggered.connect(lambda: self.del_chat(item.data(50)))
        rename_action.triggered.connect(lambda: self.rename_chat(item.data(50)))

        menu.addAction(del_action)
        menu.addAction(rename_action)

        pos = self.chats_bar.viewport().mapToGlobal(pos)
        menu.exec(pos)

    def del_chat(self, local_id):
        if id == self.chat_selected:
            self.chat_selected = None
        self.conf.db.delete_chat(local_id)
        self.update_data()

    def rename_chat(self, local_id):
        text = TextReq(self.conf, 'Введите новое название', parent=self)
        if text.exec() == QDialog.DialogCode.Accepted:
            text = text.get_text()
            self.conf.db.rename_chat(local_id, text)
        self.update_data()

    def add_chat(self):
        text = TextReq(self.conf, 'Введите название чата', parent=self)
        if text.exec() == QDialog.DialogCode.Accepted:
            text = text.get_text()
            self.conf.db.create_chat(text)

    def send_message(self):
        message = self.prompt.toPlainText()

        self.prompt.setPlainText('')

        self.chat_selected = self.conf.db.send_message(message, self.chat_selected)

    def _get_chat_by(self, local_id=None, public_id=None):
        for i in self.data['chats']:
            if i['local_id'] == local_id:
                return i
            if i['public_id'] == public_id:
                return i
        return None

    def _update_visibility(self):
        chat = self._get_chat_by(local_id=self.chat_selected)
        if chat is None:
            self.chat_selected = None
            self.no_messages_label.hide()
            self.message_bar.hide()
            self.messages_border.hide()
        else:
            self.no_messages_label.hide()
            self.messages_border.show()
            self.message_bar.show()
            if len(chat['messages']) == 0:
                self.no_messages_label.show()

            if not chat['ready']:
                self.prompt.setEnabled(False)
                self.gen_btn.setEnabled(False)
                self.gen_btn.setIcon(QIcon(self.conf.paths.icon("generate_btn")))
            else:
                self.prompt.setEnabled(True)
                self.gen_btn.setEnabled(True)
                self.gen_btn.setIcon(QIcon(self.conf.paths.icon("generate_btn_active")))

        if self.menu_opened and len(self.chats_displayed) == 0:
            self.no_chats_label.show()
        else:
            self.no_chats_label.hide()

    def _update_message_bar(self):
        chat = self._get_chat_by(local_id=self.chat_selected)
        if chat is None:
            return

        ans = ''
        for i in chat['messages']:
            if i['user_sent'] is None and '!THINKING!' in i['text']:
                ans += f'''<div class="message-block message-aporia"><div class="message-author">Апория</div>
                        <div class="message-text">{mdtex2html.convert(i['text'].split('!THINKING!')[1], extensions=['fenced_code', 'codehilite', 'tables'])}</div></div>'''
            elif ']' in i['text']:
                actual = i['text'][i['text'].index(']') + 1:]
                ans += f'''<div class="message-block message-user"><div class="message-author">Компьютер {i['user_sent']}</div>
                        <div class="message-text">{cgi.escape(actual)}</div></div>'''

        if not chat['ready']:
            ans += '''<div class="message-block message-aporia"><div class="message-author">Апория</div>
                      <div class="message-text">Думаю...</div></div>'''

        if self.messages_displayed != chat['messages']:
            styles = self.conf.paths.css(self.conf.db.settings['current_theme'])
            html = Template(self.conf.paths.html('messages')).render(messages=ans, styles=styles)

            self.message_bar.page().setBackgroundColor(QColor(0, 0, 0, 0))
            self.message_bar.setHtml(html, QUrl('file://'))

            self.messages_displayed = chat['messages'].copy()

    def settings(self):
        text = SettingsPrompt(self.conf, self)
        if text.exec() == QDialog.DialogCode.Accepted:
            data = text.get_data()
            if len(data['cluster_token']) >= 5:
                self.conf.db.set_cluster_token(data['cluster_token'])
            if len(data['about']) >= 1:
                self.conf.db.set_about(data['about'])
            self.conf.db.settings['current_theme'] = data['current_theme']
            self.conf.db._save_session()
