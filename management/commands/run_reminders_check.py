from django.core.management.base import BaseCommand
from .tasks import send_due_reminders

class Command(BaseCommand):
    help = 'Check reminders and trigger notifications if due'

    def handle(self, *args, **kwargs):
        send_due_reminders()
        self.stdout.write(self.style.SUCCESS("✅ Reminder check done."))
