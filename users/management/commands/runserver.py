from django.core.management.base import BaseCommand
from celery import Celery
from celery.apps.worker import Worker

app = Celery('src')  # Create a Celery app instance

class Command(BaseCommand):
    '''
        Added here to automate termination and restart of celery.py command
    '''
    def handle(self, *args, **options):
        worker = Worker(app=app)
        worker.start()