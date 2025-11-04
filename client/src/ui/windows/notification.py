import time

from PyQt6.QtWidgets import (QMainWindow, QPushButton,
                             QLineEdit, QTextEdit, QGraphicsOpacityEffect, QWidget, QLabel, QFrame)
from PyQt6.QtCore import Qt, QSize, QPropertyAnimation, pyqtProperty, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QTimer

conf = None


class MoveNotificationThread(QThread):
    move_window = pyqtSignal(int, int)

    def __init__(self, x_init, y_init, duration, travel):
        super().__init__()
        self.x = x_init
        self.y = y_init
        self.duration = duration
        self.travel = travel

    def run(self):
        s = time.time()
        while True:
            elapsed = time.time() - s
            if elapsed > self.duration:
                break
            self.move_window.emit(int(self.x + self.travel * (elapsed / self.duration)), self.y)


class Notification(QWidget):
    def __init__(self, config, alive_time=3, text="Готово.", title="Уведомление"):
        super().__init__()
        global conf
        conf = config

        self.alive_time = alive_time
        self.text = text
        self.title = title

        self.setupWindow()
        self.setupUi()

    def setupWindow(self):
        self.setWindowTitle(f'{conf.assistant_name} - уведомление')
        self.setFixedSize(conf.tile * 7 + 20, conf.tile * 2 + 20)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.ToolTip |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowIcon(QIcon(conf.paths.icon("icon")))
        self.setStyleSheet(conf.paths.style(conf.current_theme))

    def show_up(self):
        self.thread = MoveNotificationThread(self.x(), self.y(), 1, -self.width())
        self.thread.move_window.connect(self.move)
        self.thread.start()

    def hide_down(self):
        self.thread = MoveNotificationThread(self.x(), self.y(), 1, self.width())
        self.thread.move_window.connect(self.move)
        self.thread.start()

    def setupUi(self):
        t = conf.tile

        background = QFrame(self)
        background.setFixedSize(t * 7, t * 2)
        background.setObjectName('ContentBlock')

        self.title_label = QLabel(self.title, self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.title_label.move(int(t * 0.3), int(t * 0.3))

        self.message_label = QLabel(self.text, self)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.message_label.move(int(t * 0.3), t)
        self.message_label.setWordWrap(True)
        self.message_label.setFixedSize(int(6.4 * t), t)
        QTimer.singleShot(self.alive_time * 1000 - 1000, self.hide_down)
