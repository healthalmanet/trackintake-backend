"""
Initial migration for Food Attributes System

This migration creates the four core models:
- FoodAttribute: Master list of attributes
- FoodAttributeOption: Options for each attribute
- FoodItemAttribute: Links FoodItem to attributes
- UserMealAttribute: Stores user selections
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        # Adjust based on your actual last migration
        ('userFood', '0002_add_portion_size'),
    ]

    operations = [
        # Create FoodAttribute table
        migrations.CreateModel(
            name='FoodAttribute',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(
                    help_text='e.g., "Flour Type", "Fat Type", "Size"', max_length=100, unique=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),

        # Create FoodAttributeOption table
        migrations.CreateModel(
            name='FoodAttributeOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.CharField(
                    help_text='The option value (e.g., "Wheat", "Toned")', max_length=100)),
                ('display_name', models.CharField(blank=True, default='',
                 help_text='Human-readable display name (optional)', max_length=100)),
                ('description', models.TextField(blank=True, null=True)),
                ('nutrition_multiplier', models.FloatField(default=1.0,
                 help_text='Nutritional adjustment factor (1.0 = no change)')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('attribute', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                 related_name='options', to='userFood.foodattribute')),
            ],
            options={
                'ordering': ['attribute__name', 'value'],
                'unique_together': {('attribute', 'value')},
            },
        ),

        # Create FoodItemAttribute table
        migrations.CreateModel(
            name='FoodItemAttribute',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name='ID')),
                ('is_required', models.BooleanField(
                    default=True, help_text='If True, user must select this attribute when logging this food')),
                ('order', models.PositiveIntegerField(
                    default=0, help_text='Display order in UI')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('attribute', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, to='userFood.foodattribute')),
                ('food_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                 related_name='attributes', to='userFood.fooditem')),
            ],
            options={
                'ordering': ['order', 'attribute__name'],
                'unique_together': {('food_item', 'attribute')},
            },
        ),

        # Create UserMealAttribute table
        migrations.CreateModel(
            name='UserMealAttribute',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('attribute', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, to='userFood.foodattribute')),
                ('selected_option', models.ForeignKey(help_text="The user's selected option for this attribute",
                 on_delete=django.db.models.deletion.PROTECT, to='userFood.foodattributeoption')),
                ('user_meal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                 related_name='meal_attributes', to='userFood.usermeal')),
            ],
            options={
                'ordering': ['attribute__name'],
                'unique_together': {('user_meal', 'attribute')},
            },
        ),

        # Create indexes for performance
        migrations.AddIndex(
            model_name='fooditemattribute',
            index=models.Index(fields=['food_item_id'],
                               name='userFood_fo_food_item_idx'),
        ),
        migrations.AddIndex(
            model_name='fooditemattribute',
            index=models.Index(fields=['attribute_id'],
                               name='userFood_fo_attribut_idx'),
        ),
        migrations.AddIndex(
            model_name='usermealattribute',
            index=models.Index(fields=['user_meal_id'],
                               name='userFood_us_user_mea_idx'),
        ),
        migrations.AddIndex(
            model_name='usermealattribute',
            index=models.Index(fields=['attribute_id'],
                               name='userFood_us_attribut_idx'),
        ),
    ]
