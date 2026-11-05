from django.db import migrations


def auto_approve_pending_prices(apps, schema_editor):
    NutritionistProfile = apps.get_model('nutritionist', 'NutritionistProfile')
    profiles = NutritionistProfile.objects.all()
    for profile in profiles:
        changed = False
        if profile.pending_online_price is not None:
            profile.online_price = profile.pending_online_price
            profile.pending_online_price = None
            changed = True
        if profile.pending_offline_price is not None:
            profile.offline_price = profile.pending_offline_price
            profile.pending_offline_price = None
            changed = True
        if profile.price_approval_status != "approved":
            profile.price_approval_status = "approved"
            profile.price_rejection_reason = None
            changed = True
        if changed:
            profile.save(update_fields=[
                'online_price',
                'offline_price',
                'pending_online_price',
                'pending_offline_price',
                'price_approval_status',
                'price_rejection_reason'
            ])


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('nutritionist', '0005_nutritionistprofile_additional_certifications_and_more'),
    ]

    operations = [
        migrations.RunPython(auto_approve_pending_prices, reverse_noop),
    ]

