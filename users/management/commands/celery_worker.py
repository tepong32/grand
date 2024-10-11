from celery.bin import worker
import subprocess

class Command(worker):
    '''
        Terminates and restarts existing celery processes, making sure there will only be one instance of the commands running.
    '''
    def handle(self, *args, **options):
        # Terminate the existing Celery process
        subprocess.call(['pkill', '-f', 'celery worker'])
        print("Terminated old Celery worker process...")

        # Start the new Celery process
        worker.main(['worker', '-A', 'src'])
        print("Started new Celery worker process in the background...")