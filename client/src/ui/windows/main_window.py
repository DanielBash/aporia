import time

from PyQt6.QtWidgets import (QMainWindow, QPushButton,
                             QLineEdit, QTextEdit, QGraphicsOpacityEffect, QListWidget, QListWidgetItem, QLabel,
                             QAbstractItemView, QMenu, QGraphicsBlurEffect)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QTimer


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
                print('exeption here: ' + e)

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
        self.blur_needed = False

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

        # ДОСТУПНЫЕ ЧАТЫ: HTML
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
        self.search.textChanged.connect(self.update_chat_bar)

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
        self.no_chats_label.move(int(t * 0.5), int(t * 4))
        self.no_chats_label.setText('Нет чатов...')

        self.update_data(conf.db.get_all())

        if not conf.api_auth:
            conf.notification_manager.show_notification(title='Апория', text='Авторизация не завершена')
            self.closeWindow()

        self.update_thread = UpdateWorker(conf.db)
        self.update_thread.dataReady.connect(self.update_data)
        self.update_thread.start()

    def checkFocus(self):
        if not self.isActiveWindow() and not self.fade_applied and not self.blur_needed:
            self.fade = QGraphicsOpacityEffect(self)
            self.fade.setOpacity(0.5)
            self.setGraphicsEffect(self.fade)
            self.fade_applied = True
        else:
            if self.fade_applied and not self.blur_needed:
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

    def update_data(self, data):
        if not conf.api_auth:
            conf.notification_manager.show_notification(title='Апория', text='Авторизация не завершена')
            self.closeWindow()

        self.update_chats_data(data)

        self.update_chat_bar()

    def update_chats_data(self, data):
        data = data['chats']
        ans = []
        for i in data.keys():
            chat = {'id': i}
            chat.update(data[i])
            ans.append(chat)
        self.chats = ans

    def update_chat_bar(self):
        self.chats_bar.clear()
        for i in self.chats:
            if self.search.text().lower() in i['name'].lower():
                chat = QListWidgetItem(i['name'])
                self.chats_bar.addItem(chat)
                chat.setData(50, i["id"])
                if self.chat_selected == i["id"]:
                    self.chats_bar.setCurrentItem(chat)
                    chat.setSelected(True)
        if len(self.chats) == 0:
            self.no_chats_label.show()
        else:
            self.no_chats_label.hide()

    def select_chat(self):
        item = self.chats_bar.currentItem()
        if item:
            self.chat_selected = item.data(50)
        else:
            self.chat_selected = None

    def apply_blur(self, rad):
        self.blur_needed = True
        self.blur = QGraphicsBlurEffect()
        self.blur.setBlurRadius(rad)
        self.setGraphicsEffect(self.blur)

    def chat_item_dropdown(self, pos):
        item = self.chats_bar.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)

        self.apply_blur(10)
        del_action = QAction('Удалить чат', self)
        rename_action = QAction('Переименовать', self)
        about_action = QAction('Информация', self)

        menu.addAction(del_action)
        menu.addAction(rename_action)
        menu.addAction(about_action)

        pos = self.chats_bar.viewport().mapToGlobal(pos)
        menu.exec(pos)