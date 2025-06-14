CRONJOBS = [
    # minute hour day month weekday <command-to-execute>
    ''' this is running daily at midnight '''
    ('0 0 * * *', 'leave_mgt.cron.update_leave_credits_from_cronPy', '>> /logs/cron.log 2>&1'), # prod path: /home/abutdtks/test.abutchikikz.online/logs/cron.log 2>&1'
]

CRON_CLASSES = ['django_crontab.crontab.CronJobBase']