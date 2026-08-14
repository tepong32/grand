CRONJOBS = [
    # minute hour day month weekday <command-to-execute>

    # Run daily at midnight
    (
        '0 0 * * *',
        'leave_mgt.cron.update_leave_credits_from_cronPy',
        '>> /home/abutdtks/test.abutchikikz.online/logs/cron.log 2>&1',
    ),

    # Check the run ledger frequently; each schedule determines its own cycle.
    (
        '*/10 * * * *',
        'django.core.management.call_command',
        ['run_scheduled_reports'],
        {},
        '>> /home/abutdtks/test.abutchikikz.online/logs/reporting_cron.log 2>&1',
    ),

    # DISABLED for now
    # Run Telegram bot on system reboot
    # ('@reboot', 'telegram_bot.cron.StartTelegramBotCron >> /home/abutdtks/test.abutchikikz.online/logs/telegram_cron.log 2>&1'),
]
