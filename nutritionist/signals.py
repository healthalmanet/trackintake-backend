from django.db.models.signals import post_save
from django.dispatch import receiver
from user.models import User
from .models import NutritionistProfile, PatientAssignment

DEFAULT_NUTRITIONIST_EMAIL = "dr.rohansharma@gmail.com"

@receiver(post_save, sender=User)
def create_nutritionist_profile(sender, instance, created, **kwargs):
    if created and instance.role == 'nutritionist':
        NutritionistProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def auto_assign_default_nutritionist(sender, instance, created, **kwargs):
    if created and instance.role == 'user':
        if not PatientAssignment.objects.filter(patient=instance).exists():
            default_nutritionist = User.objects.filter(
                email=DEFAULT_NUTRITIONIST_EMAIL, role='nutritionist'
            ).first() or User.objects.filter(role='nutritionist').order_by('id').first()
            if default_nutritionist:
                PatientAssignment.objects.get_or_create(
                    patient=instance,
                    defaults={'nutritionist': default_nutritionist}
                )
