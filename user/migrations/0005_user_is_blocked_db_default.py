from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("user", "0004_user_blocked_at_user_blocked_reason_user_is_blocked_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE user_user ALTER COLUMN is_blocked SET DEFAULT false;",
            reverse_sql="ALTER TABLE user_user ALTER COLUMN is_blocked DROP DEFAULT;",
        ),
    ]
