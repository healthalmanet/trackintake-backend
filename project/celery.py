# your_project/celery.py
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')

app = Celery('project')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Add this configuration to keep the connection alive
app.conf.broker_transport_options = {
    'health_check_interval': 150,  # Send a health check every 30 seconds
    'visibility_timeout': 10000,   # Increase if you have long-running tasks
}

# Load task modules from all registered Django  app configs.
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')