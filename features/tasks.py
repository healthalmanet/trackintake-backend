# features/tasks.py

import logging
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import CustomReminder
from django.conf import settings

logger = logging.getLogger(__name__)
print(logger)

def send_and_reschedule_reminders():
    """
    This is the core task function. It is called by our secure API endpoint.
    It finds due reminders, sends notifications, and reschedules for the future.
    """
    logger.info("✅ Task started: Checking for due reminders...")

    channel_layer = get_channel_layer()
    if channel_layer is None:
        print("❌ Channel layer is None! WebSocket notifications will fail.")
        logger.error("❌ Channel layer is None! WebSocket notifications will fail.")
    
    now = timezone.now()

    # Find all active reminders where the next due time is now or in the past
    reminders_to_send = CustomReminder.objects.filter(next_due_at__lte=now, is_active=True)

    if not reminders_to_send.exists():
        logger.info("✅ No due reminders found.")
        print("✅ No due reminders found.")
        return

    logger.info(f"📌 Found {reminders_to_send.count()} due reminders to process.")
    print(f"📌 Found {reminders_to_send.count()} due reminders to process.")

    for reminder in reminders_to_send:
        user = reminder.user
        message = f"⏰ Reminder: {reminder.title}"
        group_name = f"user_{user.id}"

        logger.info(f"🔔 Processing reminder '{reminder.title}' for user {user.email}")
        print(f"🔔 Processing reminder '{reminder.title}' for user {user.email}")

        # 1. Send Gmail Notification
        try:
            send_mail(
                subject=f"Your Reminder: {reminder.title}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,  # Uses EMAIL_HOST_USER from settings.py
                recipient_list=[user.email],
                fail_silently=False
            )
            logger.info(f"📧 Email sent to {user.email} for reminder '{reminder.title}'.")
            print(f"📧 Email sent to {user.email} for reminder '{reminder.title}'.")
        except Exception as e:
            logger.error(f"❌ Failed to send email to {user.email}: {e}")
            print(f"❌ Failed to send email to {user.email}: {e}")

        # 2. Send WebSocket Push Notification via the channel layer
        if channel_layer:
            try:
                async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "send_reminder",
                    "message": message,
                    "reminder_id": reminder.id,
                    "title": reminder.title
                }
            )
                print(f"📲 WebSocket message sent to group '{group_name}'.")
                logger.info(f"📲 WebSocket message sent to group '{group_name}'.")
            except Exception as e:
                logger.error(f"❌ WebSocket send failed for user {user.id}: {e}")
                print(f"❌ WebSocket send failed for user {user.id}: {e}")
        else:
            logger.warning(f"⚠️ Skipping WebSocket send for user {user.id} due to missing channel layer.")
            print(f"⚠️ Skipping WebSocket send for user {user.id} due to missing channel layer.")

        # 3. Reschedule or Deactivate the Reminder
        if reminder.frequency == 'once':
            reminder.is_active = False
            logger.info(f"✅ Deactivated 'once' reminder: {reminder.title}")
            print(f"✅ Deactivated 'once' reminder: {reminder.title}")
        else:
            if reminder.frequency == 'daily':
                reminder.next_due_at += timedelta(days=1)
            elif reminder.frequency == 'weekly':
                reminder.next_due_at += timedelta(weeks=1)
            logger.info(f"🔄 Rescheduled {reminder.frequency} reminder '{reminder.title}' to {reminder.next_due_at}")
            print(f"🔄 Rescheduled {reminder.frequency} reminder '{reminder.title}' to {reminder.next_due_at}")

        reminder.save()

    logger.info(f"✅ Task finished. Processed {reminders_to_send.count()} reminders.")
    print(f"✅ Task finished. Processed {reminders_to_send.count()} reminders.")










def send_message_notification(sender, receiver, text):
    channel_layer = get_channel_layer()
    message = f"📩 New message from {sender.full_name or sender.email}: {text}"

    # Gmail
    try:
        send_mail(
            subject="New Message Notification",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[receiver.email],
            fail_silently=False,
        )
        logger.info(f"📧 Email sent to {receiver.email}")
    except Exception as e:
        logger.error(f"❌ Email failed: {e}")

    # WebSocket
    try:
        async_to_sync(channel_layer.group_send)(
        f"user_{receiver.id}",
        {
            "type": "send_message",
            "message": text,
            "sender_id": sender.id,
            "sender_name": sender.full_name,
            "sender_email": sender.email,
            "receiver_id": receiver.id,
            "receiver_name": receiver.full_name,
            "receiver_email": receiver.email
        }
    )

        logger.info(f"📲 WebSocket sent to user {receiver.id}")
    except Exception as e:
        logger.error(f"❌ WebSocket failed: {e}")








# def send_message_notification(sender, receiver, text):
    # channel_layer = get_channel_layer()
    # message = f"📩 New message from {sender.full_name}: {text}"

    # # 1. Gmail Notification
    # try:
    #     send_mail(
    #         subject="New Message Notification",
    #         message=message,
    #         from_email="health.almanet@gmail.com",
    #         recipient_list=[receiver.email],
    #         fail_silently=False,
    #     )
    #     logger.info(f"📧 Email sent to {receiver.email}")
    #     print(f"📧 Email sent to {receiver.email}")
    # except Exception as e:
    #     logger.error(f"❌ Email failed: {e}")
    #     print(f"❌ Email failed: {e}")

    # # 2. WebSocket Notification
    # try:
    #     async_to_sync(channel_layer.group_send)(
    #         f"user_{receiver.id}",
    #         {
    #             "type": "send_message",
    #             "message": text,
    #             "sender_id": sender.id,
    #             "receiver_id": receiver.id
    #         }
    #     )
    #     logger.info(f"📲 WebSocket message sent to {receiver.id}")
    #     print(f"📲 WebSocket message sent to {receiver.id}")
    # except Exception as e:
    #     logger.error(f"❌ WebSocket failed: {e}")
    #     print(f"❌ WebSocket failed: {e}")