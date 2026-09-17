import importlib
import platform
import re
import shlex
import subprocess
import sys
from pathlib import Path


# Expands a hand-written expected command using only the active interpreter and source location
def runtime_command(command, prefix=None):
    module = importlib.import_module("instagram_monitor")
    assert module.__file__ is not None
    manual = [sys.executable, str(Path(module.__file__).resolve())]
    packaged = [sys.executable, "-m", "instagram_monitor"]
    windows = platform.system() == "Windows"
    quote = subprocess.list2cmdline if windows else shlex.join
    manual_prefix = prefix if prefix is not None else quote(manual)
    packaged_prefix = prefix if prefix is not None else quote(packaged)
    command = re.sub(r"(?<![\w/])python(?:3(?:\.\d+)?)? instagram_monitor\.py", lambda match: manual_prefix, command)
    return re.sub(r"(?<![\w/])instagram_monitor(?= |$)", lambda match: packaged_prefix, command)
