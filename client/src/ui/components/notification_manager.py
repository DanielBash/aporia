from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtWidgets import QApplication
from ..windows.notification import Notification


def position_notification(notification):
    screen_geometry = QApplication.primaryScreen().availableGeometry()

    x = screen_geometry.right()
    y = screen_geometry.bottom() - notification.height()

    notification.move(x, y)


class Manager(QObject):
    def __init__(self, conf, parent=None):
        super().__init__(parent)
        self.notification_queue = []
        self.conf = conf
        self.current_notification = None

    def show_notification(self, text='Готово.', title='Уведомление'):
        if not self.conf.notifications_on:
            return
        self.notification_queue.append({'text': text, 'title': title})
        if not self.current_notification and QApplication.instance() is not None:
            self.show_next()

    def show_next(self):
        if self.current_notification:
            self.current_notification.hide()
            self.current_notification.close()
            self.current_notification.destroy()
            self.current_notification = None
        if len(self.notification_queue) == 0:
            return
        data = self.notification_queue[0]
        self.notification_queue = self.notification_queue[1:]
        self.current_notification = Notification(self.conf, text=data['text'], title=data['title'],
                                                 alive_time=self.conf.notification_alive_time)
        self.current_notification.show()
        position_notification(self.current_notification)
        self.current_notification.show_up()
        QTimer.singleShot(self.conf.notification_alive_time * 1000, self.show_next)
