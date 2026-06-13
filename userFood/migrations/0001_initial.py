# Hand-written initial migration to match the existing DB schema (without portion_size).
# Apply with: python manage.py migrate userFood 0001 --fake

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Allergen",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=50, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name="FoodType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=30, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name="MealType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=40, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name="FoodItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(help_text="The unique name of the food item.", max_length=150, unique=True)),
                ("default_quantity", models.FloatField(default=1, help_text="e.g., 1, 2, 100")),
                ("default_unit", models.CharField(default="piece", help_text="e.g., piece, cup, bowl, g", max_length=20)),
                ("gram_equivalent", models.FloatField(blank=True, help_text="The equivalent weight in grams for the default serving (e.g., 1 cup = 240g)", null=True)),
                ("calories", models.FloatField(help_text="Calories (kcal)")),
                ("protein", models.FloatField(help_text="Protein in grams")),
                ("carbs", models.FloatField(help_text="Carbohydrates in grams")),
                ("fats", models.FloatField(help_text="Total Fat in grams")),
                ("sugar", models.FloatField(blank=True, help_text="Sugar in grams", null=True)),
                ("fiber", models.FloatField(blank=True, help_text="Fiber in grams", null=True)),
                ("saturated_fat_g", models.FloatField(blank=True, null=True, verbose_name="Saturated Fat (g)")),
                ("trans_fat_g", models.FloatField(blank=True, null=True, verbose_name="Trans Fat (g)")),
                ("estimated_gi", models.FloatField(blank=True, null=True, verbose_name="Estimated Glycemic Index")),
                ("glycemic_load", models.FloatField(blank=True, null=True, verbose_name="Glycemic Load")),
                ("sodium_mg", models.FloatField(blank=True, null=True, verbose_name="Sodium (mg)")),
                ("potassium_mg", models.FloatField(blank=True, null=True, verbose_name="Potassium (mg)")),
                ("iron_mg", models.FloatField(blank=True, null=True, verbose_name="Iron (mg)")),
                ("calcium_mg", models.FloatField(blank=True, null=True, verbose_name="Calcium (mg)")),
                ("iodine_mcg", models.FloatField(blank=True, null=True, verbose_name="Iodine (mcg)")),
                ("zinc_mg", models.FloatField(blank=True, null=True, verbose_name="Zinc (mg)")),
                ("magnesium_mg", models.FloatField(blank=True, null=True, verbose_name="Magnesium (mg)")),
                ("selenium_mcg", models.FloatField(blank=True, null=True, verbose_name="Selenium (mcg)")),
                ("cholesterol_mg", models.FloatField(blank=True, null=True, verbose_name="Cholesterol (mg)")),
                ("omega_3_g", models.FloatField(blank=True, null=True, verbose_name="Omega-3 (g)")),
                ("vitamin_d_mcg", models.FloatField(blank=True, null=True, verbose_name="Vitamin D (mcg)")),
                ("vitamin_b12_mcg", models.FloatField(blank=True, null=True, verbose_name="Vitamin B12 (mcg)")),
                ("fodmap_level", models.CharField(choices=[("Low","Low"),("Medium","Medium"),("High","High"),("Moderate","Moderate"),("Mild","Mild"),("None","None")], default="Low", max_length=10, verbose_name="FODMAP Level")),
                ("spice_level", models.CharField(choices=[("Low","Low"),("Medium","Medium"),("High","High"),("Moderate","Moderate"),("Mild","Mild"),("None","None")], default="Low", max_length=10, verbose_name="Spice Level")),
                ("purine_level", models.CharField(choices=[("Low","Low"),("Medium","Medium"),("High","High"),("Moderate","Moderate"),("Mild","Mild"),("None","None")], default="Low", max_length=10, verbose_name="Purine Level")),
                ("is_verified", models.BooleanField(default=False, help_text="True if data has been manually verified.")),
                ("source_url", models.URLField(blank=True, help_text="URL of the nutritional data source (e.g., USDA).", max_length=512, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("allergens", models.ManyToManyField(blank=True, related_name="food_items", to="userFood.allergen")),
                ("food_types", models.ManyToManyField(blank=True, related_name="food_items", to="userFood.foodtype")),
                ("meal_types", models.ManyToManyField(blank=True, related_name="food_items", to="userFood.mealtype")),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="UserMeal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("food_name", models.CharField(blank=True, max_length=150, null=True)),
                ("quantity", models.FloatField()),
                ("unit", models.CharField(choices=[("Gram","Gram"),("Kilogram","Kilogram"),("Milliliters","Milliliters"),("Liters","Liters"),("Cup","Cup"),("Bowl","Bowl"),("Piece","Piece"),("Tbsp","Tablespoon"),("Tsp","Teaspoon"),("Slice","Slice"),("Plate","Plate"),("Handful","Handful"),("Pinch","Pinch"),("Dash","Dash"),("Sprinkle","Sprinkle"),("Other","Other")], default="Gram", max_length=20)),
                ("meal_type", models.CharField(choices=[("Early-Morning","Early-Morning"),("Breakfast","Breakfast"),("Mid-Morning Snack","Mid-Morning Snack"),("Lunch","Lunch"),("Afternoon Snack","Afternoon Snack"),("Dinner","Dinner"),("Bedtime","Bedtime")], max_length=30)),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("date", models.DateField(blank=True, null=True)),
                ("remarks", models.TextField(blank=True)),
                ("calories", models.FloatField(blank=True, null=True)),
                ("protein", models.FloatField(blank=True, null=True)),
                ("carbs", models.FloatField(blank=True, null=True)),
                ("fats", models.FloatField(blank=True, null=True)),
                ("sugar", models.FloatField(blank=True, null=True)),
                ("fiber", models.FloatField(blank=True, null=True)),
                ("estimated_gi", models.FloatField(blank=True, null=True)),
                ("glycemic_load", models.FloatField(blank=True, null=True)),
                ("food_type", models.CharField(blank=True, max_length=30, null=True)),
                ("food_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="userFood.fooditem")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
