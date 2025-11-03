import sys
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QCursor, QIcon
from PyQt6.QtCore import QTimer
import keyboard
from config import config as conf
from src.ui.windows import main_window


class MainApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setApplicationVersion(conf.application_version)

        self.window = None
        self.needWindow = False
        self.showWindowCenter = False

        self.windowNeeds = QTimer()
        self.windowNeeds.timeout.connect(self.showWindow)
        self.windowNeeds.start(100)

        if conf.enable_shortcut:
            keyboard.add_hotkey(conf.open_window_shortcut, self.timeToShowWindow)

        self.setupTray()

        conf.notification_manager.show_notification(title='Апория', text='Приложение запущено')

    def setupTray(self):
        menu = QMenu()
        exit_action = menu.addAction("Выключить")
        open_action = menu.addAction("Открыть")
        settings_action = menu.addAction("Настройки")

        exit_action.triggered.connect(self.exit)
        open_action.triggered.connect(self.timeToShowWindowCenter)
        settings_action.triggered.connect(self.timeToShowWindowCenter)

        tray = QSystemTrayIcon(QIcon(conf.paths.icon('icon_active')), self.app)
        tray.activated.connect(self.tray)
        tray.setContextMenu(menu)
        tray.show()

    def tray(self, q):
        if q == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.timeToShowWindowCenter()

    def showWindow(self):
        if not self.needWindow:
            return
        if self.window is None or self.window.needs_destroy:
            pos = QCursor.pos()
            screen = QApplication.primaryScreen()
            if self.showWindowCenter:
                cp =  screen.availableGeometry().center()
                self.window = main_window.MainWindow(conf, (cp.x(), cp.y()))
            else:
                self.window = main_window.MainWindow(conf, (pos.x(), pos.y()))
            self.window.show()
            self.window.activateWindow()
            self.window.raise_()
            self.needWindow = False

    def timeToShowWindow(self):
        self.needWindow = True
        self.showWindowCenter = False

    def timeToShowWindowCenter(self):
        self.needWindow = True
        self.showWindowCenter = True

    def run(self):
        sys.exit(self.app.exec())

    def exit(self):
        self.app.quit()


if __name__ == "__main__":
    app = MainApp()
    app.run()
