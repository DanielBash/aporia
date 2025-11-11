from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QDialog, QLineEdit


class SettingsPrompt(QDialog):
    def __init__(self, conf, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGraphicsEffect(None)
        self.conf = conf

        self.setStyleSheet(conf.paths.style(conf.db.settings['current_theme']))
        self.setFixedSize(conf.tile * 8, conf.tile * 9)

        self.cluster_token_input = QLineEdit(self)
        self.cluster_token_input.setPlaceholderText('Присоединиться к кластеру')
        self.cluster_token_input.setFixedSize(conf.tile * 7, conf.tile)
        self.cluster_token_input.returnPressed.connect(self.accept)

        self.ok_btn = QPushButton(self)
        self.ok_btn.setToolTip('Подтвердить')
        self.ok_btn.setFixedSize(conf.tile, conf.tile)
        self.ok_btn.move(conf.tile * 7, 0)
        self.ok_btn.setIcon(QIcon(conf.paths.icon("generate_btn")))
        self.ok_btn.setIconSize(QSize(int(conf.tile * 0.7), int(conf.tile * 0.7)))
        self.ok_btn.clicked.connect(self.accept)

        self.cluster_token = QLineEdit(self)
        self.cluster_token.setText(conf.db.session_data['cluster_token'])
        self.cluster_token.setReadOnly(True)
        self.cluster_token.setFixedSize(conf.tile * 7, conf.tile)
        self.cluster_token.move(0, conf.tile)

    def get_text(self):
        return self.cluster_token_input.text()