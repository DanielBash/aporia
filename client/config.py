import sys
from pathlib import Path
from dataclasses import dataclass


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
        self.database_dir = self.data_dir / "instance"

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

    server_host = 'aporia.ibashlhr.beget.tech'
    server_port = 80

    feed_check_timeout = 1

    # Path settings
    paths = Paths()

    # Database settings
    db = None

    # Networking settings
    api = None

    # Asset settings
    assets = None

    # Notification settings
    notification_manager = None
    notifications_on = True
    notification_alive_time = 5

    # User settings
    open_window_shortcut = 'ctrl+shift+h'
    enable_shortcut = True

    current_theme = 'light'
    tile = 40
