import os
import subprocess
import sys
from pathlib import Path
import venv


def execute(script, conf):
    try:
        workspace = Path(conf.paths.workspace_dir)
        os.makedirs(workspace, exist_ok=True)
        venv_dir = workspace / "venv"
        if not (venv_dir / "bin" / "python").exists() and not (venv_dir / "Scripts" / "python.exe").exists():
            venv.EnvBuilder(with_pip=True).create(venv_dir)
        (workspace / "execution.py").write_text(script, encoding="utf-8")
        if sys.platform == "win32":
            python = venv_dir / "Scripts" / "python.exe"
        else:
            python = venv_dir / "bin" / "python"
        res = subprocess.run([str(python), str(workspace / "execution.py")], capture_output=True, text=True,
                             encoding='utf-8', errors='replace', timeout=30)
        return res.stdout + res.stderr
    except Exception as e:
        return str(e)
