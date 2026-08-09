from __future__ import annotations

from pathlib import Path
import os
from django.conf import settings


def resolve_bot_token():
    return os.getenv('TELEGRAM_BOT_TOKEN')


def resolve_python_binary():
    return os.getenv('TELEGRAM_BOT_PYTHON', 'python')


def resolve_bot_script_path():
    return str(Path(settings.BASE_DIR) / 'telegram_bot' / 'bot_handler.py')


def resolve_log_file_path():
    return str(Path(settings.BASE_DIR) / 'logs' / 'telegram_bot.log')
