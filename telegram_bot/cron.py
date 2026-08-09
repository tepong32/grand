import subprocess
from pathlib import Path
from telegram_bot.services.bot_config import resolve_bot_script_path, resolve_log_file_path, resolve_python_binary

class StartTelegramBotCron:
    def run(self):
        python_bin = resolve_python_binary()
        bot_script = resolve_bot_script_path()
        log_file = resolve_log_file_path()

        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        log_handle = open(log_file, "a", encoding="utf-8")
        subprocess.Popen(
            [python_bin, bot_script],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
