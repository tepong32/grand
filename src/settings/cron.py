CRONJOBS = [
    # minute hour day month weekday <command-to-execute>

    # Run daily at midnight
    ('0 0 * * *', 'leave_mgt.cron.update_leave_credits_from_cronPy >> /home/abutdtks/test.abutchikikz.online/logs/cron.log 2>&1'),

    # Run Telegram bot on system reboot
    ('@reboot', 'telegram_bot.cron.StartTelegramBotCron >> /home/abutdtks/test.abutchikikz.online/logs/telegram_cron.log 2>&1'),
]
    