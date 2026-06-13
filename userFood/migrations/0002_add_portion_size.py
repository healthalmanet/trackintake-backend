from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("userFood", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="usermeal",
            name="portion_size",
            field=models.CharField(
                blank=True,
                choices=[("Small", "Small"), ("Medium", "Medium"), ("Large", "Large")],
                default="Medium",
                max_length=10,
            ),
        ),
    ]
