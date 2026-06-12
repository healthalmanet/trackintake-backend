from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.forms import ValidationError
from django.utils import timezone
from django.conf import settings



###################################_---------------------------------Normalize----------##################################

# --- Level Choices ---
LEVEL_CHOICES = [
    ("Low", "Low"),
    ("Medium", "Medium"),
    ("High", "High"),
    ("Moderate", "Moderate"),
    ("Mild", "Mild"),
    ("None", "None"),
]


# --- Food Type Master ---
class FoodType(models.Model):
    name = models.CharField(max_length=30, unique=True)  # Vegetarian, Vegan, Non-Vegetarian, etc.

    def __str__(self):
        return self.name

# --- Meal Type Master ---
class MealType(models.Model):
    name = models.CharField(max_length=40, unique=True)  # Breakfast, Lunch, Dinner, Snack, etc.

    def __str__(self):
        return self.name

# --- Allergen Master ---
class Allergen(models.Model):
    name = models.CharField(max_length=50, unique=True)  # Gluten, Dairy, Nuts, etc.

    def __str__(self):
        return self.name

# --- Food Item Core Model (Optimized) ---
class FoodItem(models.Model):
    # --- Basic Info & Serving ---
    name = models.CharField(max_length=150, unique=True, help_text="The unique name of the food item.")
    default_quantity = models.FloatField(default=1, help_text="e.g., 1, 2, 100")
    default_unit = models.CharField(max_length=20, default="piece", help_text="e.g., piece, cup, bowl, g")
    gram_equivalent = models.FloatField(null=True, blank=True, help_text="The equivalent weight in grams for the default serving (e.g., 1 cup = 240g)")

    # --- Core Macronutrients (per default serving) ---
    calories = models.FloatField(help_text="Calories (kcal)")
    protein = models.FloatField(help_text="Protein in grams")
    carbs = models.FloatField(help_text="Carbohydrates in grams")
    fats = models.FloatField(help_text="Total Fat in grams")
    sugar = models.FloatField(null=True, blank=True, help_text="Sugar in grams")
    fiber = models.FloatField(null=True, blank=True, help_text="Fiber in grams")

    # --- Fat Profile (per default serving) ---
    saturated_fat_g = models.FloatField(null=True, blank=True, verbose_name="Saturated Fat (g)")
    trans_fat_g = models.FloatField(null=True, blank=True, verbose_name="Trans Fat (g)")

    # --- Glycemic Data ---
    estimated_gi = models.FloatField(null=True, blank=True, verbose_name="Estimated Glycemic Index")
    glycemic_load = models.FloatField(null=True, blank=True, verbose_name="Glycemic Load")

    # --- Minerals (per default serving, values can be null if not present) ---
    sodium_mg = models.FloatField(null=True, blank=True, verbose_name="Sodium (mg)")
    potassium_mg = models.FloatField(null=True, blank=True, verbose_name="Potassium (mg)")
    iron_mg = models.FloatField(null=True, blank=True, verbose_name="Iron (mg)")
    calcium_mg = models.FloatField(null=True, blank=True, verbose_name="Calcium (mg)")
    iodine_mcg = models.FloatField(null=True, blank=True, verbose_name="Iodine (mcg)")
    zinc_mg = models.FloatField(null=True, blank=True, verbose_name="Zinc (mg)")
    magnesium_mg = models.FloatField(null=True, blank=True, verbose_name="Magnesium (mg)")
    selenium_mcg = models.FloatField(null=True, blank=True, verbose_name="Selenium (mcg)")

    # --- Vitamins & Other Nutrients (per default serving) ---
    cholesterol_mg = models.FloatField(null=True, blank=True, verbose_name="Cholesterol (mg)")
    omega_3_g = models.FloatField(null=True, blank=True, verbose_name="Omega-3 (g)")
    vitamin_d_mcg = models.FloatField(null=True, blank=True, verbose_name="Vitamin D (mcg)")
    vitamin_b12_mcg = models.FloatField(null=True, blank=True, verbose_name="Vitamin B12 (mcg)")

    # --- Classification & Suitability ---
    fodmap_level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default="Low", verbose_name="FODMAP Level")
    spice_level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default="Low", verbose_name="Spice Level")
    purine_level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default="Low", verbose_name="Purine Level")

    # --- Relationships (Simplified using ManyToManyField) ---
    food_types = models.ManyToManyField(FoodType, blank=True, related_name="food_items")
    meal_types = models.ManyToManyField(MealType, blank=True, related_name="food_items")
    allergens = models.ManyToManyField(Allergen, blank=True, related_name="food_items")

    # --- Data Verification (CRITICAL for ML & User Trust) ---
    is_verified = models.BooleanField(default=False, help_text="True if data has been manually verified.")
    source_url = models.URLField(max_length=512, null=True, blank=True, help_text="URL of the nutritional data source (e.g., USDA).")
    
    # --- Timestamps ---
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name'] # Good practice to have a default order

    def __str__(self):
        return self.name


###############################----------------------------Foood Table End_---------------------################################
MASS_UNIT_TO_GRAMS = {
    "g": 1.0, "gram": 1.0,
    "kg": 1000.0, "kilogram": 1000.0,
    "mg": 0.001, "milligram": 0.001,
}

class UserMeal(models.Model):
    """
    Represents a single meal entry for a user.
    The nutritional values are a snapshot calculated at the time of saving.
    """
    # --- These Choices must be exactly the same ---
    UNIT_CHOICES = [
        ("Gram", "Gram"), ("Kilogram", "Kilogram"), ("Milliliters", "Milliliters"),
        ("Liters", "Liters"), ("Cup", "Cup"), ("Bowl", "Bowl"), ("Piece", "Piece"),
        ("Tbsp", "Tablespoon"), ("Tsp", "Teaspoon"), ("Slice", "Slice"),
        ("Plate", "Plate"), ("Handful", "Handful"), ("Pinch", "Pinch"),
        ("Dash", "Dash"), ("Sprinkle", "Sprinkle"), ("Other", "Other"),
    ]
    MEAL_CHOICES = [
       ("Early-Morning", "Early-Morning"), ("Breakfast", "Breakfast"),
       ("Mid-Morning Snack", "Mid-Morning Snack"), ("Lunch", "Lunch"),
       ("Afternoon Snack", "Afternoon Snack"), ("Dinner", "Dinner"),
       ("Bedtime", "Bedtime"),
    ]

    # --- These Core Fields must be exactly the same ---
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    food_item = models.ForeignKey('FoodItem', on_delete=models.SET_NULL, null=True, blank=True)
    food_name = models.CharField(max_length=150, blank=True, null=True)

    quantity = models.FloatField()
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default="Gram")
    meal_type = models.CharField(max_length=30, choices=MEAL_CHOICES)

    consumed_at = models.DateTimeField(blank=True, null=True)
    date = models.DateField(blank=True, null=True)
    remarks = models.TextField(blank=True)

    # --- These Nutritional Snapshot Fields must be exactly the same ---
    calories = models.FloatField(blank=True, null=True)
    protein = models.FloatField(blank=True, null=True)
    carbs = models.FloatField(blank=True, null=True)
    fats = models.FloatField(blank=True, null=True)
    sugar = models.FloatField(blank=True, null=True)
    fiber = models.FloatField(blank=True, null=True)
    estimated_gi = models.FloatField(blank=True, null=True)
    glycemic_load = models.FloatField(blank=True, null=True)
    food_type = models.CharField(max_length=30, blank=True, null=True)

    # --- THIS IS THE ONLY PART WITH DIFFERENT LOGIC ---
    def _calculate_and_set_nutrients(self):
        """
        Calculates nutrients based on a flexible, two-path system.
        """
        if not self.food_item:
            return

        food_item = self.food_item
        user_quantity = self.quantity
        user_unit_lower = self.unit.lower()

        factor = 1.0

        if user_unit_lower in MASS_UNIT_TO_GRAMS:
            # Mass-based unit: scale by grams relative to gram_equivalent.
            # If gram_equivalent is missing/zero, fall back to default_quantity as the base serving.
            base_grams = food_item.gram_equivalent if (food_item.gram_equivalent and food_item.gram_equivalent > 0) \
                else (food_item.default_quantity or 1.0)
            conversion_to_grams = MASS_UNIT_TO_GRAMS[user_unit_lower]
            logged_grams = user_quantity * conversion_to_grams
            factor = logged_grams / base_grams
        else:
            factor = user_quantity

        def calc(value):
            return round(value * factor, 2) if value is not None else None

        self.calories = calc(food_item.calories)
        self.protein = calc(food_item.protein)
        self.carbs = calc(food_item.carbs)
        self.fats = calc(food_item.fats)
        self.sugar = calc(food_item.sugar)
        self.fiber = calc(food_item.fiber)
        self.estimated_gi = food_item.estimated_gi
        self.glycemic_load = calc(food_item.glycemic_load)
        self.food_type = food_item.food_types.first().name if food_item.food_types.exists() else 'N/A'

    # --- These helper methods must be exactly the same ---
    def save(self, *args, **kwargs):
        """
        Overrides save to ensure data is always consistent and calculated correctly.
        """
        if self.food_item:
            if not self.food_name:
                self.food_name = self.food_item.name
            self._calculate_and_set_nutrients()

        if not self.consumed_at:
            self.consumed_at = timezone.now()
        
        if not self.date:
            self.date = self.consumed_at.date()
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.get_username()}'s {self.get_meal_type_display()} on {self.date}"