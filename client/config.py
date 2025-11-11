import sys
from pathlib import Path
from dataclasses import dataclass

from src.api import Api
from src.database import Database
from src.ui.components.notification_manager import Manager


@dataclass
class Paths:
    """Manage all application paths"""

    def __init__(self):
        if getattr(sys, 'frozen', False):
            self.root_dir = Path(sys.executable).parent
        else:
            self.root_dir = Path(__file__).parent

        self.data_dir = self.root_dir / "data"
        self.assets_dir = self.root_dir / "assets"

        self.workspace_dir = self.data_dir / "workspace"
        self.database_dir = self.data_dir / "instance" / 'db.sqlite'

        self.icons_dir = self.assets_dir / "icons"
        self.style_dir = self.assets_dir / "styles"
        self.html_dir = self.assets_dir / "html"

    def icon(self, name):
        return str(self.icons_dir / (name + '.png'))

    def style(self, name, extract_text=True):
        directory = self.style_dir / (name + '.qss')
        if extract_text:
            return directory.read_text()
        else:
            return directory

    def css(self, name, extract_text=True):
        directory = self.style_dir / (name + '.css')
        if extract_text:
            return directory.read_text()
        else:
            return directory

    def html(self, name, extract_text=True):
        directory = self.html_dir / (name + '.html')
        if extract_text:
            return directory.read_text()
        else:
            return directory


@dataclass
class Config:
    """General application settings and common variable references"""

    # Main settings
    assistant_name = 'Апория'
    application_version = '1.0.0'

    server_host = 'https://aporia.ibashlhr.beget.tech/api'

    server_pull_interval = 1

    # Notification settings
    notifications_on = True
    notification_alive_time = 5

    # User settings
    enable_shortcut = False
    tile = 40
    default_chat_name = 'Новый чат'

    default_settings = {
        "notifications": True,
        "open_window_shortcut": "ctrl+shift+h",
        "current_theme": "light",
    }

    def __init__(self):
        self.paths = Paths()
        self.notification_manager = Manager(self)
        self.api = Api(self)
        self.db = Database(self)


# Creating config instance
config = Config()
