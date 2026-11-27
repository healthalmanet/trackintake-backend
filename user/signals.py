from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from .blocking import deactivate_block_records_for_user, sync_block_record_for_user

User = get_user_model()


@receiver(post_save, sender=User)
def sync_blocked_user_contacts(sender, instance, **kwargs):
    """Keep BlockedContact synchronized whenever a User is blocked/deactivated or unblocked."""
    if getattr(instance, "is_blocked", False) or not getattr(instance, "is_active", True):
        sync_block_record_for_user(instance, reason=getattr(instance, "blocked_reason", "") or "")
    else:
        deactivate_block_records_for_user(instance)


@receiver(pre_delete, sender=User)
def preserve_blocked_contacts_on_delete(sender, instance, **kwargs):
    """Ensure blocked email/phone records remain active even if the User row is deleted."""
    if getattr(instance, "is_blocked", False) or not getattr(instance, "is_active", True):
        sync_block_record_for_user(instance, reason=getattr(instance, "blocked_reason", "") or "")


@receiver(post_save, sender="userProfile.UserProfile")
def sync_blocked_profile_mobile(sender, instance, **kwargs):
    """If a blocked user's profile mobile_number is saved/updated, record it in BlockedContact."""
    user = getattr(instance, "user", None)
    if user and (getattr(user, "is_blocked", False) or not getattr(user, "is_active", True)):
        sync_block_record_for_user(user, reason=getattr(user, "blocked_reason", "") or "")

