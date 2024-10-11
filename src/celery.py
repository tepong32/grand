from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab 

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'src.settings') 

app = Celery('src') 
app.config_from_object('django.conf:settings', namespace='CELERY') 
app.autodiscover_tasks() 

app.conf.beat_schedule = {
    'update-leave-credits': {
        'task': 'src.tasks.update_leave_credits',
        # Runs daily at a specific time (e.g., 12:02 AM)
        'schedule': crontab(hour=0, minute=2, day_of_month='1'), 
    },
}