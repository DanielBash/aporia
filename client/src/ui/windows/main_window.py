from PyQt6.QtWidgets import (QMainWindow, QPushButton,
                             QLineEdit, QTextEdit, QGraphicsOpacityEffect)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QTimer


conf = None


class MainWindow(QMainWindow):
    def __init__(self, config, pos=(0, 0)):
        super().__init__()
        global conf

        conf = config

        self.tile = 40
        self.changed = False
        self.menu_opened = True

        self.prompt = None
        self.gen_btn = None
        self.menu_btn = None
        self.message_bar = None
        self.search = None
        self.add_chat_btn = None
        self.close_btn = None
        self.chats_bar = None

        self.focus = QTimer()
        self.fade = QGraphicsOpacityEffect(self)

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

        self.setGraphicsEffect(self.fade)

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
        self.chats_bar = QPushButton(self)
        self.chats_bar.setFixedSize(t * 4, t * 7 - 2)
        self.chats_bar.move(0, t + 1)

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

    def checkFocus(self):
        if not self.isActiveWindow():
            if not self.changed:
                self.hide()
                self.destroy()
            else:
                self.fade.setOpacity(0.5)
        else:
            self.fade.setOpacity(1)

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
            self.hide()
            self.destroy()

    def closeWindow(self):
        self.hide()
        self.destroy()