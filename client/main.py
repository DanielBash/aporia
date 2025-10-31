import random
import sys
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon
from PyQt6.QtGui import QCursor, QIcon
from PyQt6.QtCore import QTimer
import keyboard
from pynput import keyboard
from config import Config as conf
from src.ui.windows import main_window
from src.database import Database
from src.api import Api
from src.ui.components.notification_manager import Manager


class MainApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setApplicationVersion(conf.application_version)

        self.window = None
        self.setupTray()
        self.needWindow = False

        if conf.enable_shortcut:
            keyboard.add_hotkey(conf.open_window_shortcut, self.timeToShowWindow)

        self.windowNeeds = QTimer()
        self.windowNeeds.timeout.connect(self.showWindow)
        self.windowNeeds.start(100)

        conf.db = Database()
        conf.api = Api()
        conf.notification_manager = Manager(conf)
        conf.notification_manager.show_notification(title='Апория', text='Приложение запушено')

    def setupTray(self):
        tray = QSystemTrayIcon(QIcon(conf.paths.icon('icon')), self.app)
        tray.activated.connect(self.tray)
        tray.show()

    def tray(self, q):
        if q == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.timeToShowWindow()

    def showWindow(self):
        if not self.needWindow:
            return
        if self.window is None or not self.window.isActiveWindow():
            pos = QCursor.pos()
            self.window = main_window.MainWindow(conf, (pos.x(), pos.y()))
            self.window.show()
            self.window.activateWindow()
            self.window.raise_()
            self.needWindow = False

    def timeToShowWindow(self):
        self.needWindow = True

    def run(self):
        sys.exit(self.app.exec())


if __name__ == "__main__":
    app = MainApp()
    app.run()
