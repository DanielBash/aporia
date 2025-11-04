import time

import mdtex2html
from PyQt6 import QtCore
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (QMainWindow, QPushButton,
                             QLineEdit, QTextEdit, QGraphicsOpacityEffect, QListWidget, QListWidgetItem, QLabel,
                             QAbstractItemView, QMenu, QGraphicsBlurEffect, QDialog, QFrame, QWidget, QVBoxLayout,
                             QScrollArea, QTextBrowser)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QRect, QUrl
from PyQt6.QtGui import QIcon, QAction, QPainterPath, QColor
from PyQt6.QtCore import QTimer
import threading

from client.src.ui.components.prompt_edit import PromptEdit
from client.src.ui.windows.input_popup import TextReq
import markdown
from jinja2 import Template
import html as cgi

conf = None


class UpdateWorker(QThread):
    dataReady = pyqtSignal(dict)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.running = True

    def run(self):
        while self.running:
            time.sleep(0.5)
            try:
                self.dataReady.emit(self.db.get_all())
            except Exception as e:
                print(e)

    def stop(self):
        self.running = False


class MainWindow(QMainWindow):
    def __init__(self, config, pos=(0, 0)):
        super().__init__()
        global conf

        conf = config

        self.tile = 40
        self.changed = False
        self.menu_opened = True
        self.fade_applied = False
        self.needs_destroy = False

        self.prompt = None
        self.gen_btn = None
        self.menu_btn = None
        self.message_bar = None
        self.search = None
        self.add_chat_btn = None
        self.close_btn = None
        self.chats_bar = None
        self.no_chats_label = None

        self.chats = []
        self.chat_selected = None
        self.messages_displayed = [{'id': 0, 'text': 'blag'}]

        self.focus = QTimer()

        self.setupWindow(pos)
        self.setupUi()
        self.toggleMenu()

    def setupWindow(self, pos):
        self.setWindowTitle(f'{conf.assistant_name}')
        self.setFixedSize(self.tile * 13, self.tile * 9)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.move(int(pos[0] - self.tile * 8.5), int(pos[1] - self.tile * 8.5))
        self.setWindowIcon(QIcon(conf.paths.icon("icon_active")))

        self.focus.timeout.connect(self.checkFocus)
        self.focus.start(100)

        self.setStyleSheet(conf.paths.style(conf.current_theme))

    def setupUi(self):
        t = self.tile

        # МЕНЮ ОТКРЫТЬ: КНОПКА
        self.menu_btn = QPushButton(self)

        self.menu_btn.setFixedSize(t, t)
        self.menu_btn.move(t * 4, t * 8)

        self.menu_btn.setToolTip('Все чаты')
        self.menu_btn.setIcon(QIcon(conf.paths.icon("menu_btn")))
        self.menu_btn.setIconSize(QSize(int(t * 0.7), int(t * 0.7)))
        self.menu_btn.clicked.connect(self.toggleMenu)

        # ГЕНЕРАЦИЯ: КНОПКА
        self.gen_btn = QPushButton(self)

        self.gen_btn.setFixedSize(t, t)
        self.gen_btn.move(t * 12, t * 8)

        self.gen_btn.setToolTip('Отправить команду')
        self.gen_btn.setIcon(QIcon(conf.paths.icon("generate_btn_active")))
        self.gen_btn.setIconSize(QSize(int(t * 0.7), int(t * 0.7)))
        self.gen_btn.clicked.connect(self.sendMessage)

        # ДОБАВИТЬ ЧАТ: КНОПКА
        self.add_chat_btn = QPushButton(self)

        self.add_chat_btn.setFixedSize(t * 4, t)
        self.add_chat_btn.move(0, t * 8)

        self.add_chat_btn.setToolTip('Добавить чат')
        self.add_chat_btn.setIcon(QIcon(conf.paths.icon("add_chat_btn_active")))
        self.add_chat_btn.setIconSize(QSize(int(t * 0.7), int(t * 0.7)))

        self.add_chat_btn.clicked.connect(self.addChat)

        # ДОСТУПНЫЕ ЧАТЫ
        self.chats_bar = QListWidget(self)
        self.chats_bar.setFixedSize(t * 4, t * 7 - 2)
        self.chats_bar.move(0, t + 1)
        self.chats_bar.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chats_bar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chats_bar.itemClicked.connect(self.selectChat)
        self.chats_bar.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.chats_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.chats_bar.customContextMenuRequested.connect(self.chatItemDropdown)

        # ЗКАРЫТЬ: КНОПКА
        self.close_btn = QPushButton(self)

        self.close_btn.setFixedSize(t, t)
        self.close_btn.move(0, 0)

        self.close_btn.setToolTip('Закрыть приложение')
        self.close_btn.setIcon(QIcon(conf.paths.icon("close_btn_active")))
        self.close_btn.setIconSize(QSize(int(t * 0.7), int(t * 0.7)))
        self.close_btn.clicked.connect(self.closeWindow)

        # ПОИСК: ПОЛЕ ВВОДА
        self.search = QLineEdit(self)

        self.search.setFixedSize(t * 3, t)
        self.search.move(t, 0)

        self.search.setPlaceholderText(f"🔍 Поиск")
        self.search.textChanged.connect(self.updateChatBar)

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

        self.prompt.setPlaceholderText(f"{conf.assistant_name} ждет команды...")
        self.prompt.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.prompt.textChanged.connect(self.promptEdited)
        self.prompt.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.prompt.returnPressed.connect(self.sendMessage)
        QTimer.singleShot(50, self.prompt.setFocus)

        if not conf.api_auth:
            conf.notification_manager.show_notification(title='Апория', text='Авторизация не завершена')
            self.closeWindow()

        self.update_thread = UpdateWorker(conf.db)
        self.update_thread.dataReady.connect(self.updateData)
        self.update_thread.start()

        self.updateData(conf.db.get_all())

    def checkFocus(self):
        if not self.isActiveWindow() and not self.fade_applied:
            self.fade = QGraphicsOpacityEffect(self)
            self.fade.setOpacity(0.5)
            self.setGraphicsEffect(self.fade)
            self.fade_applied = True
        else:
            if self.fade_applied and self.isActiveWindow():
                self.setGraphicsEffect(None)
                self.fade_applied = False

    def toggleMenu(self):
        if self.menu_opened:
            self.menu_btn.setIcon(QIcon(conf.paths.icon("menu_btn")))
            self.close_btn.hide()
            self.search.hide()
            self.chats_bar.hide()
            self.add_chat_btn.hide()
        else:
            self.menu_btn.setIcon(QIcon(conf.paths.icon("active_menu_btn")))
            self.close_btn.show()
            self.search.show()
            self.chats_bar.show()
            self.add_chat_btn.show()
        self.menu_opened = not self.menu_opened

    def promptEdited(self):
        t = self.tile
        self.changed = True
        h = self.prompt.document().size().height()
        h = max(min(int(h) + 5, 120), t)
        if h != self.prompt.height():
            self.prompt.setFixedHeight(h)
        self.prompt.move(t * 5, t * 8 + 40 - h)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.closeWindow()

    def closeWindow(self):
        if hasattr(self, 'update_thread'):
            self.update_thread.stop()
        self.needs_destroy = True
        self.deleteLater()

    def updateData(self, data):
        if not conf.api_auth:
            conf.notification_manager.show_notification(title='Апория', text='Авторизация не завершена')
            self.closeWindow()
        self.updateChatsData(data)

        self.updateChatBar()
        if self.chat_selected:
            self.updateMessageBar()

    def updateChatsData(self, data):
        data = data['chats']
        ans = []
        for i in data.keys():
            chat = {'id': i}
            chat.update(data[i])
            ans.append(chat)
        self.chats = ans

    def updateChatBar(self):
        self.chats_bar.clearSelection()
        existing_items_by_id = {}
        for row in range(self.chats_bar.count()):
            item = self.chats_bar.item(row)
            item_id = item.data(50)
            existing_items_by_id[item_id] = item
        desired_ids = set()
        search_text = self.search.text().lower()
        for chat_info in self.chats:
            if search_text in chat_info['name'].lower():
                desired_ids.add(chat_info['id'])

                if chat_info['id'] not in existing_items_by_id:
                    new_item = QListWidgetItem(chat_info['name'])
                    new_item.setData(50, chat_info['id'])
                    self.chats_bar.addItem(new_item)
                    existing_items_by_id[chat_info['id']] = new_item
                else:
                    existing_item = existing_items_by_id[chat_info['id']]
                    if chat_info['name'] != existing_item.text():
                        existing_item.setText(chat_info['name'])
        for item_id, item in list(existing_items_by_id.items()):
            if item_id not in desired_ids:
                row = self.chats_bar.row(item)
                self.chats_bar.takeItem(row)
        if self.chat_selected and self.chat_selected in desired_ids:
            for row in range(self.chats_bar.count()):
                item = self.chats_bar.item(row)
                if item.data(50) == self.chat_selected:
                    self.chats_bar.setCurrentItem(item)
                    item.setSelected(True)
                    break
        if self.chat_selected:
            self.message_bar.show()
            self.messages_border.show()
        else:
            self.message_bar.hide()
            self.messages_border.hide()
            self.no_messages_label.hide()
        if not desired_ids and self.menu_opened:
            self.no_chats_label.show()
        else:
            self.no_chats_label.hide()

    def selectChat(self):
        item = self.chats_bar.currentItem()
        if item:
            self.chat_selected = item.data(50)

    def chatItemDropdown(self, pos):
        item = self.chats_bar.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)

        del_action = QAction('Удалить чат', self)
        rename_action = QAction('Переименовать', self)

        del_action.triggered.connect(lambda: self.delChat(item.data(50)))
        rename_action.triggered.connect(lambda: self.renameChat(item.data(50)))

        menu.addAction(del_action)
        menu.addAction(rename_action)

        pos = self.chats_bar.viewport().mapToGlobal(pos)
        menu.exec(pos)

    def updateTheme(self):
        self.setStyleSheet(conf.paths.style(conf.current_theme))

    def delChat(self, id):
        if id == self.chat_selected:
            self.chat_selected = None
            self.chats_bar.clearSelection()
        threading.Thread(target=lambda: conf.db.delete_chat(id), daemon=True).start()

    def renameChat(self, id):
        text = TextReq(conf, 'Введите новое название', parent=self)
        if text.exec() == QDialog.DialogCode.Accepted:
            text = text.get_text()
            threading.Thread(target=lambda: conf.db.rename_chat(id, text), daemon=True).start()

    def addChat(self):
        text = TextReq(conf, 'Введите название чата', parent=self)
        if text.exec() == QDialog.DialogCode.Accepted:
            text = text.get_text()
            threading.Thread(target=lambda: conf.db.create_chat(text), daemon=True).start()

    def sendMessage(self):
        message = self.prompt.toPlainText()
        self.prompt.setText('')
        if self.chat_selected:
            threading.Thread(target=lambda: conf.db.send_message(message, self.chat_selected), daemon=True).start()
        else:
            new_chat_id = conf.db.send_new(message)
            QTimer.singleShot(1000, lambda: self.sendMessageSelectChat(new_chat_id))

    def sendMessageSelectChat(self, chat_id):
        self.chat_selected = chat_id
        self.updateData(conf.db.get_all())

    def updateMessageBar(self):
        chat_data = None
        for i in range(len(self.chats)):
            if self.chats[i]['id'] == self.chat_selected:
                chat_data = self.chats[i]
                break
        if chat_data is None:
            self.chat_selected = None
            return
        if self.messages_displayed == chat_data['messages']:
            return
        ans = ''
        for i in chat_data['messages']:
            if i['user_sent'] is None and '!THINKING!' in i['text']:
                ans += f'''<div class="message-block message-aporia"><div class="message-author">Апория</div>
                        <div class="message-text">{mdtex2html.convert(i['text'].split('!THINKING!')[1], extensions=['fenced_code', 'codehilite'])}</div></div>'''
            elif ']' in i['text']:
                actual = i['text'][i['text'].index(']') + 1:]
                ans += f'''<div class="message-block message-user"><div class="message-author">Компьютер {i['user_sent']}</div>
                        <div class="message-text">{cgi.escape(actual)}</div></div>'''
        if not chat_data['ready']:
            ans += '''<div class="message-block message-aporia"><div class="message-author">Апория</div>
                      <div class="message-text">Думаю/Выполняю код. Может занять до 5-ти минут</div></div>'''
        if len(chat_data['messages']) == 0:
            self.no_messages_label.show()
        else:
            self.no_messages_label.hide()
        styles = conf.paths.css(conf.current_theme)
        html = Template(conf.paths.html('messages')).render(messages=ans, styles=styles)
        self.message_bar.page().setBackgroundColor(QColor(0, 0, 0, 0))
        self.message_bar.setHtml(html, QUrl('file://'))
        self.messages_displayed = chat_data['messages'].copy()
        if not chat_data['ready']:
            self.prompt.setEnabled(False)
            self.gen_btn.setEnabled(False)
            self.gen_btn.setIcon(QIcon(conf.paths.icon("generate_btn")))
        else:
            self.prompt.setEnabled(True)
            self.gen_btn.setEnabled(True)
            self.gen_btn.setIcon(QIcon(conf.paths.icon("generate_btn_active")))
