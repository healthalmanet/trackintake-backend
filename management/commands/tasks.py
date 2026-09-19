from utils.resend_email import send_resend_email_async

def send_due_reminders():
    reminders = CustomReminder.objects.filter(reminder_time__lte=now(), is_active=True)

    channel_layer = get_channel_layer()
    for reminder in reminders:
        user = reminder.user
        msg = f"⏰ Reminder: {reminder.title}"

        # ✅ Send Resend Email Notification
        if user and user.email:
            send_resend_email_async(
                to=user.email,
                subject="⏰ Your Reminder Notification",
                text=msg,
                html=f"<p>{msg}</p>"
            )

        # ✅ Send WebSocket if user online
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",
            {"type": "send_reminder", "message": msg}
        )

        reminder.is_active = False  # optional: disable after triggering
        reminder.save()
