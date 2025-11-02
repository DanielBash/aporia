import time

from PyQt6.QtWidgets import (QMainWindow, QPushButton,
                             QLineEdit, QTextEdit, QGraphicsOpacityEffect, QListWidget, QListWidgetItem, QLabel,
                             QAbstractItemView, QMenu, QGraphicsBlurEffect, QDialog)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QTimer
import threading
from client.src.ui.windows.input_popup import TextReq

conf = None


class UpdateWorker(QThread):
    dataReady = pyqtSignal(dict)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.running = True

    def run(self):
        while self.running:
            time.sleep(1)
            try:
                data = self.db.get_all()
                self.dataReady.emit(data)
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
        self.setWindowIcon(QIcon(conf.paths.icon("icon")))

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
        self.gen_btn.setIcon(QIcon(conf.paths.icon("generate_btn")))
        self.gen_btn.setIconSize(QSize(int(t * 0.7), int(t * 0.7)))

        # ДОБАВИТЬ ЧАТ: КНОПКА
        self.add_chat_btn = QPushButton(self)

        self.add_chat_btn.setFixedSize(t * 4, t)
        self.add_chat_btn.move(0, t * 8)

        self.add_chat_btn.setToolTip('Добавить чат')
        self.add_chat_btn.setIcon(QIcon(conf.paths.icon("add_chat_btn")))
        self.add_chat_btn.setIconSize(QSize(int(t * 0.7), int(t * 0.7)))

        self.add_chat_btn.clicked.connect(self.addChat)

        # ДОСТУПНЫЕ ЧАТЫ: HTML
        self.chats_bar = QListWidget(self)
        self.chats_bar.setFixedSize(t * 4, t * 7 - 2)
        self.chats_bar.move(0, t + 1)
        self.chats_bar.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chats_bar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chats_bar.itemSelectionChanged.connect(self.selectChat)
        self.chats_bar.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.chats_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.chats_bar.customContextMenuRequested.connect(self.chatItemDropdown)

        # ЗКАРЫТЬ: КНОПКА
        self.close_btn = QPushButton(self)

        self.close_btn.setFixedSize(t, t)
        self.close_btn.move(0, 0)

        self.close_btn.setToolTip('Закрыть приложение')
        self.close_btn.setIcon(QIcon(conf.paths.icon("close_btn")))
        self.close_btn.setIconSize(QSize(int(t * 0.7), int(t * 0.7)))
        self.close_btn.clicked.connect(self.closeWindow)

        # ПОИСК: ПОЛЕ ВВОДА
        self.search = QLineEdit(self)

        self.search.setFixedSize(t * 3, t)
        self.search.move(t, 0)

        self.search.setPlaceholderText(f"🔍 Поиск")
        self.search.textChanged.connect(self.updateChatBar)

        # ТЕКУЩИЙ ЧАТ: ПОЛЕ
        self.message_bar = QPushButton(self)

        self.message_bar.setFixedSize(t * 9, t * 8 - 1)
        self.message_bar.move(t * 4 + 1, 0)

        self.message_bar.hide()

        # ЗАПРОС: ПОЛЕ ВВОДА
        self.prompt = QTextEdit(self)

        self.prompt.setFixedSize(t * 7, t)
        self.prompt.move(t * 5, t * 8)

        self.prompt.setPlaceholderText(f"{conf.assistant_name} ждет команды...")
        self.prompt.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.prompt.textChanged.connect(self.promptEdited)
        self.prompt.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        QTimer.singleShot(50, self.prompt.setFocus)

        # ПОДСКАЗКА: НЕТ ЧАТОВ
        self.no_chats_label = QLabel(self)
        self.no_chats_label.move(int(t * 1), int(t * 4))
        self.no_chats_label.setText('Нет чатов...')

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
            if self.fade_applied:
                if self.isActiveWindow():
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
        self.update_thread.stop()
        self.hide()
        self.destroy()
        self.needs_destroy = True

    def updateData(self, data):
        if not conf.api_auth:
            conf.notification_manager.show_notification(title='Апория', text='Авторизация не завершена')
            self.closeWindow()

        self.updateChatsData(data)

        self.updateChatBar()

    def updateChatsData(self, data):
        data = data['chats']
        ans = []
        for i in data.keys():
            chat = {'id': i}
            chat.update(data[i])
            ans.append(chat)
        self.chats = ans

    def updateChatBar(self):
        existing_items_by_id = {}
        for row in range(self.chats_bar.count()):
            item = self.chats_bar.item(row)
            item_id = item.data(50)
            existing_items_by_id[item_id] = item

        desired_ids = set()
        for chat_info in self.chats:
            if self.search.text().lower() in chat_info['name'].lower():
                desired_ids.add(chat_info['id'])
                if chat_info['id'] not in existing_items_by_id:
                    new_item = QListWidgetItem(chat_info['name'])
                    new_item.setData(50, chat_info['id'])
                    self.chats_bar.addItem(new_item)
                    if self.chat_selected == chat_info['id']:
                        self.chats_bar.setCurrentItem(new_item)
                        new_item.setSelected(True)
                if chat_info['id'] in existing_items_by_id:
                    if chat_info['name'] != existing_items_by_id[chat_info['id']].text():
                        existing_items_by_id[chat_info['id']].setText(chat_info['name'])

        for item_id, item in list(existing_items_by_id.items()):
            if item_id not in desired_ids:
                row = self.chats_bar.row(item)
                taken = self.chats_bar.takeItem(row)

        if not desired_ids and self.menu_opened:
            self.no_chats_label.show()
        else:
            self.no_chats_label.hide()

    def selectChat(self):
        item = self.chats_bar.currentItem()
        if item:
            self.chat_selected = item.data(50)
        else:
            self.chat_selected = None

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
        threading.Thread(target=lambda: conf.db.delete_chat(id), daemon=True).start()

    def renameChat(self, id):
        text = TextReq(conf, 'Введите новое название', parent=self)
        if text.exec() == QDialog.DialogCode.Accepted:
            text = text.get_text()
            existing_items_by_id = {}
            for row in range(self.chats_bar.count()):
                item = self.chats_bar.item(row)
                item_id = item.data(50)
                existing_items_by_id[item_id] = item
            if id in existing_items_by_id.keys():
                existing_items_by_id[id].setText(text)
            threading.Thread(target=lambda: conf.db.rename_chat(id, text), daemon=True).start()

    def addChat(self):
        text = TextReq(conf, 'Введите название чата', parent=self)
        if text.exec() == QDialog.DialogCode.Accepted:
            text = text.get_text()
            threading.Thread(target=lambda: conf.db.create_chat(text), daemon=True).start()