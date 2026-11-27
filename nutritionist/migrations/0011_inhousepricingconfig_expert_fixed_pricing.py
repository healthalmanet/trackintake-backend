from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nutritionist', '0010_inhousepricingconfig_expert_commission_percent_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    ALTER TABLE nutritionist_inhousepricingconfig
                    ADD COLUMN IF NOT EXISTS expert_fixed_pricing_enabled BOOLEAN DEFAULT FALSE,
                    ADD COLUMN IF NOT EXISTS expert_online_price NUMERIC(10, 2) DEFAULT 999.00,
                    ADD COLUMN IF NOT EXISTS expert_offline_price NUMERIC(10, 2) DEFAULT 999.00;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='inhousepricingconfig',
                    name='expert_fixed_pricing_enabled',
                    field=models.BooleanField(
                        default=False,
                        help_text='When enabled, Expert specialists use the platform-controlled fixed online/offline rates for Fixed Price Slots (Variable Case Slots remain nutritionist-controlled).',
                        verbose_name='Enforce Fixed Consultation Rates for Expert Fixed Slots',
                    ),
                ),
                migrations.AddField(
                    model_name='inhousepricingconfig',
                    name='expert_online_price',
                    field=models.DecimalField(
                        decimal_places=2,
                        default=999.0,
                        help_text='Enforced consultation fee for expert virtual Fixed Price Slots when enabled',
                        max_digits=10,
                        verbose_name='Fixed Expert Online Rate (₹)',
                    ),
                ),
                migrations.AddField(
                    model_name='inhousepricingconfig',
                    name='expert_offline_price',
                    field=models.DecimalField(
                        decimal_places=2,
                        default=999.0,
                        help_text='Enforced consultation fee for expert in-clinic Fixed Price Slots when enabled',
                        max_digits=10,
                        verbose_name='Fixed Expert In-Clinic Rate (₹)',
                    ),
                ),
            ],
        ),
    ]

