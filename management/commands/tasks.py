from django.utils.timezone import now
from django.core.mail import send_mail
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from features.models import CustomReminder

def send_due_reminders():
    reminders = CustomReminder.objects.filter(reminder_time__lte=now(), is_active=True)

    channel_layer = get_channel_layer()
    for reminder in reminders:
        user = reminder.user
        msg = f"⏰ Reminder: {reminder.title}"

        # ✅ Send Gmail
        send_mail(
            subject="Your Reminder Notification",
            message=msg,
            from_email="health.almanet@gmail.com",
            recipient_list=[user.email],
            fail_silently=True
        )

        # ✅ Send WebSocket if user online
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",
            {"type": "send_reminder", "message": msg}
        )

        reminder.is_active = False  # optional: disable after triggering
        reminder.save()
