from PyQt6.QtWidgets import QTabWidget, QWidget, QLabel, QComboBox
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
        self.conf = conf

        self.setStyleSheet(conf.paths.style(conf.db.settings['current_theme']))
        self.setFixedSize(conf.tile * 8, conf.tile * 9)

        self.cluster_token_input = QLineEdit(self)
        self.cluster_token_input.setPlaceholderText('Присоединиться к кластеру')
        self.cluster_token_input.setFixedSize(conf.tile * 8, conf.tile)

        self.ok_btn = QPushButton(self)
        self.ok_btn.setToolTip('Подтвердить')
        self.ok_btn.setFixedSize(conf.tile * 8, conf.tile)
        self.ok_btn.move(0, conf.tile * 8)
        self.ok_btn.setIcon(QIcon(conf.paths.icon("generate_btn_active")))
        self.ok_btn.setIconSize(QSize(int(conf.tile * 0.7), int(conf.tile * 0.7)))
        self.ok_btn.clicked.connect(self.accept)

        self.cluster_token = QLineEdit(self)
        self.cluster_token.setText(conf.db.session_data['cluster_token'])
        self.cluster_token.setReadOnly(True)
        self.cluster_token.setFixedSize(conf.tile * 8, conf.tile)
        self.cluster_token.move(0, conf.tile)

        self.tab_widget = QTabWidget(self)
        self.tab_widget.setFixedSize(conf.tile * 8, conf.tile * 6)
        self.tab_widget.move(0, conf.tile * 2)

        self.change_about = None
        self.theme_select = None

        self._setup_computer_tabs()

    def get_data(self):
        return {'cluster_token': self.cluster_token_input.text(),
                'about': self.change_about.text(),
                'current_theme': self.theme_select.currentText()}

    def _setup_computer_tabs(self):
        for i in self.conf.db.users:
            computer_tab = QWidget()
            if i['about'] is None:
                i['about'] = ''
            online_text = int(i['last_online'])
            if online_text > 3:
                online_text = 'ОФФЛАЙН'
            else:
                online_text = 'ОНЛАЙН'
            text = f"Статус: {online_text}\nО компьютере: {i['about']}"
            QLabel(text=text, parent=computer_tab)
            tab_name = f"Компьютер: {i['user_id']}"
            if i['user_id'] == self.conf.db.session_data['user_id']:
                tab_name = 'Этот компьютер'
                self.change_about = QLineEdit(computer_tab)
                self.change_about.setPlaceholderText('Поменять описание')
                self.change_about.setFixedSize(self.conf.tile * 8, self.conf.tile)
                self.change_about.move(0, 50)
                if i['about'] != 'пусто.':
                    self.change_about.setText(i['about'])

                self.theme_select = QComboBox(computer_tab)
                self.theme_select.setFixedSize(self.conf.tile * 8, self.conf.tile)
                self.theme_select.move(0, 100)

                styles_path = self.conf.paths.style_dir
                filenames = sorted(list(set([f.stem for f in styles_path.iterdir() if f.is_file()])))
                self.theme_select.addItems(filenames)

                style_index = filenames.index(self.conf.db.settings['current_theme'])
                self.theme_select.setCurrentIndex(style_index)


            self.tab_widget.addTab(computer_tab, tab_name)
