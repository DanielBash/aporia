from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QDialog, QLineEdit


class TextReq(QDialog):
    def __init__(self, conf, prompt="Введите название", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Текстовый Запрос")
        self.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.conf = conf

        self.setStyleSheet(conf.paths.style(conf.current_theme))
        self.setFixedSize(conf.tile * 8, conf.tile)

        self.ans = QLineEdit(self)
        self.ans.setPlaceholderText(prompt)
        self.ans.setFixedSize(conf.tile * 7, conf.tile)
        self.ans.returnPressed.connect(self.accept)
        self.ans.setFocus()

        self.ok_btn = QPushButton(self)
        self.ok_btn.setToolTip('Подтвердить')
        self.ok_btn.setFixedSize(conf.tile, conf.tile)
        self.ok_btn.move(conf.tile * 7, 0)
        self.ok_btn.setIcon(QIcon(conf.paths.icon("generate_btn")))
        self.ok_btn.setIconSize(QSize(int(conf.tile * 0.7), int(conf.tile * 0.7)))
        self.ok_btn.clicked.connect(self.accept)

    def get_text(self):
        return self.ans.text()
