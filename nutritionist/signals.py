from django.db.models.signals import post_save
from django.dispatch import receiver
from user.models import User
from .models import NutritionistProfile

# @receiver(post_save, sender=User)
# def create_nutritionist_profile(sender, instance, created, **kwargs):
#     if created and instance.role == 'NUTRITIONIST':
#         NutritionistProfile.objects.create(user=instance)
@receiver(post_save, sender=User)
def create_nutritionist_profile(sender, instance, created, **kwargs):
    if created and instance.role == 'nutritionist':
        NutritionistProfile.objects.create(user=instance)
