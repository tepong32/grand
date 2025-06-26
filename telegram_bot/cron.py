import subprocess
import os
from django.conf import settings

class StartTelegramBotCron:
    def run(self):
        # Absolute paths on production
        python_bin = "/home/abutdtks/virtualenv/test.abutchikikz.online/3.11/bin/python"
        bot_script = "/home/abutdtks/test.abutchikikz.online/telegram_bot/bot_handler.py"
        log_file = "/home/abutdtks/test.abutchikikz.online/logs/telegram_bot.log"

        # Run the bot in background via nohup
        cmd = f"nohup {python_bin} {bot_script} >> {log_file} 2>&1 &"
        subprocess.Popen(cmd, shell=True)
