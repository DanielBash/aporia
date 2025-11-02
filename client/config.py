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

    def icon(self, name):
        return str(self.icons_dir / (name + '.png'))

    def style(self, name, extract_text=True):
        dir = self.style_dir / (name + '.qss')
        if extract_text:
            return dir.read_text()
        else:
            return dir


@dataclass
class Config:
    """General application settings"""

    # Main settings
    assistant_name = 'Апория'
    application_version = '1.0.0'

    server_host = 'https://aporia.ibashlhr.beget.tech/api'
    server_port = 80

    feed_check_timeout = 1

    # Path settings
    paths = Paths()

    # Notification settings
    notification_manager = None
    notifications_on = True
    notification_alive_time = 5

    # Network debug
    api_auth = False

    # User settings
    open_window_shortcut = 'ctrl+shift+h'
    enable_shortcut = False

    current_theme = 'dark'
    tile = 40

    def __init__(self):
        self.notification_manager = Manager(self)
        self.api = Api(self)
        self.db = Database(self)

config = Config()