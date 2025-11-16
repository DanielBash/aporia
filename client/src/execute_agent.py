import os
import subprocess
import sys
from pathlib import Path


def execute(script, conf):
    try:
        workspace = Path(conf.paths.workspace_dir)
        os.makedirs(workspace, exist_ok=True)
        venv_dir = workspace / "venv"

        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE
        else:
            startupinfo = None

        if not (venv_dir / "bin" / "python").exists() and not (venv_dir / "Scripts" / "python.exe").exists():
            subprocess.run(['python', "-m", "pip", "install", "virtualenv"],
                           startupinfo=startupinfo, capture_output=True)
            subprocess.run(['python', "-m", "virtualenv", str(venv_dir)],
                           startupinfo=startupinfo, capture_output=True)

        current_dir = Path(__file__).parent
        utils_source = current_dir / "utils.py"
        utils_destination = workspace / "utils.py"

        if utils_source.exists() and not utils_destination.exists():
            utils_content = utils_source.read_text(encoding="utf-8")
            processed_content = utils_content.replace(
                '%user_id', str(conf.db.session_data.get('user_id', ''))
            ).replace(
                '%user_token', str(conf.db.session_data['user_token'])
            ).replace(
                '%domain_name', str(conf.server_host)
            )
            utils_destination.write_text(processed_content, encoding="utf-8")

        filename = str(hash(script)) + '.py'
        (workspace / filename).write_text(script, encoding="utf-8")

        if sys.platform == "win32":
            python = venv_dir / "Scripts" / "python.exe"
        else:
            python = venv_dir / "bin" / "python"
        print('done')

        res = subprocess.run([str(python), str(workspace / filename)],
                             capture_output=True, text=True,
                             encoding='utf-8', timeout=30,
                             startupinfo=startupinfo)
        return res.stdout
    except Exception as e:
        return str(e)