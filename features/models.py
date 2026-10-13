from django.db import models
from django.utils import timezone
from django.conf import settings

from cloudinary_storage.storage import MediaCloudinaryStorage


from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


class WeightLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField()
    weight_kg = models.FloatField()
    time_logged = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-date', '-time_logged']

    def __str__(self):
        return f"{self.user} - {self.date} - {self.weight_kg} kg"


@receiver(post_save, sender=WeightLog)
def sync_profile_on_weight_save(sender, instance, **kwargs):
    if getattr(instance, '_skip_profile_sync', False):
        return
    try:
        from userProfile.models import UserProfile
        latest_log = WeightLog.objects.filter(user=instance.user).order_by('-date', '-time_logged').first()
        if latest_log:
            profile = UserProfile.objects.filter(user=instance.user).first()
            if profile and profile.weight_kg != latest_log.weight_kg:
                profile.weight_kg = latest_log.weight_kg
                profile.save(update_fields=['weight_kg'])
    except Exception:
        pass


@receiver(post_delete, sender=WeightLog)
def sync_profile_on_weight_delete(sender, instance, **kwargs):
    try:
        from userProfile.models import UserProfile
        latest_log = WeightLog.objects.filter(user=instance.user).order_by('-date', '-time_logged').first()
        profile = UserProfile.objects.filter(user=instance.user).first()
        if profile:
            new_weight = latest_log.weight_kg if latest_log else None
            if profile.weight_kg != new_weight:
                profile.weight_kg = new_weight
                profile.save(update_fields=['weight_kg'])
    except Exception:
        pass



class WaterIntakeLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='water_logs')
    amount_ml = models.PositiveIntegerField()
    date = models.DateField(default=timezone.now)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.user.email} - {self.amount_ml} ml on {self.date}"


class CustomReminder(models.Model):
    FREQUENCY_CHOICES = [
        ('once', 'Once'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('custom', 'Custom')
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reminders')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    reminder_time = models.TimeField()
    next_due_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True, # Add index for faster lookups by our task
        help_text="The exact datetime the next notification is due."
    )

    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='daily')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.user.email}"
    

class Message(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='sent_messages', on_delete=models.CASCADE)
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='received_messages', on_delete=models.CASCADE)
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"From {self.sender} to {self.receiver} at {self.timestamp}"
    

class Blog(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='blogs')
    title = models.CharField(max_length=255)
    content = models.TextField()
    image = models.ImageField(upload_to='features/blog_images/',storage=MediaCloudinaryStorage(), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
    