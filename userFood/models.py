from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.forms import ValidationError
from django.utils import timezone
from django.conf import settings


################################### _---------------------------------Normalize----------##################################

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
    # Vegetarian, Vegan, Non-Vegetarian, etc.
    name = models.CharField(max_length=30, unique=True)

    def __str__(self):
        return self.name

# --- Meal Type Master ---


class MealType(models.Model):
    # Breakfast, Lunch, Dinner, Snack, etc.
    name = models.CharField(max_length=40, unique=True)

    def __str__(self):
        return self.name

# --- Allergen Master ---


class Allergen(models.Model):
    # Gluten, Dairy, Nuts, etc.
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

# --- Food Item Core Model (Optimized) ---


class FoodItem(models.Model):
    # --- Basic Info & Serving ---
    name = models.CharField(max_length=150, unique=True,
                            help_text="The unique name of the food item.")
    default_quantity = models.FloatField(
        default=1, help_text="e.g., 1, 2, 100")
    default_unit = models.CharField(
        max_length=20, default="piece", help_text="e.g., piece, cup, bowl, g")
    gram_equivalent = models.FloatField(
        null=True, blank=True, help_text="The equivalent weight in grams for the default serving (e.g., 1 cup = 240g)")

    # --- Core Macronutrients (per default serving) ---
    calories = models.FloatField(help_text="Calories (kcal)")
    protein = models.FloatField(help_text="Protein in grams")
    carbs = models.FloatField(help_text="Carbohydrates in grams")
    fats = models.FloatField(help_text="Total Fat in grams")
    sugar = models.FloatField(null=True, blank=True,
                              help_text="Sugar in grams")
    fiber = models.FloatField(null=True, blank=True,
                              help_text="Fiber in grams")

    # --- Fat Profile (per default serving) ---
    saturated_fat_g = models.FloatField(
        null=True, blank=True, verbose_name="Saturated Fat (g)")
    trans_fat_g = models.FloatField(
        null=True, blank=True, verbose_name="Trans Fat (g)")

    # --- Glycemic Data ---
    estimated_gi = models.FloatField(
        null=True, blank=True, verbose_name="Estimated Glycemic Index")
    glycemic_load = models.FloatField(
        null=True, blank=True, verbose_name="Glycemic Load")

    # --- Minerals (per default serving, values can be null if not present) ---
    sodium_mg = models.FloatField(
        null=True, blank=True, verbose_name="Sodium (mg)")
    potassium_mg = models.FloatField(
        null=True, blank=True, verbose_name="Potassium (mg)")
    iron_mg = models.FloatField(
        null=True, blank=True, verbose_name="Iron (mg)")
    calcium_mg = models.FloatField(
        null=True, blank=True, verbose_name="Calcium (mg)")
    iodine_mcg = models.FloatField(
        null=True, blank=True, verbose_name="Iodine (mcg)")
    zinc_mg = models.FloatField(
        null=True, blank=True, verbose_name="Zinc (mg)")
    magnesium_mg = models.FloatField(
        null=True, blank=True, verbose_name="Magnesium (mg)")
    selenium_mcg = models.FloatField(
        null=True, blank=True, verbose_name="Selenium (mcg)")

    # --- Vitamins & Other Nutrients (per default serving) ---
    cholesterol_mg = models.FloatField(
        null=True, blank=True, verbose_name="Cholesterol (mg)")
    omega_3_g = models.FloatField(
        null=True, blank=True, verbose_name="Omega-3 (g)")
    vitamin_d_mcg = models.FloatField(
        null=True, blank=True, verbose_name="Vitamin D (mcg)")
    vitamin_b12_mcg = models.FloatField(
        null=True, blank=True, verbose_name="Vitamin B12 (mcg)")

    # --- Classification & Suitability ---
    fodmap_level = models.CharField(
        max_length=10, choices=LEVEL_CHOICES, default="Low", verbose_name="FODMAP Level")
    spice_level = models.CharField(
        max_length=10, choices=LEVEL_CHOICES, default="Low", verbose_name="Spice Level")
    purine_level = models.CharField(
        max_length=10, choices=LEVEL_CHOICES, default="Low", verbose_name="Purine Level")

    # --- Relationships (Simplified using ManyToManyField) ---
    food_types = models.ManyToManyField(
        FoodType, blank=True, related_name="food_items")
    meal_types = models.ManyToManyField(
        MealType, blank=True, related_name="food_items")
    allergens = models.ManyToManyField(
        Allergen, blank=True, related_name="food_items")

    # --- Data Verification (CRITICAL for ML & User Trust) ---
    is_verified = models.BooleanField(
        default=False, help_text="True if data has been manually verified.")
    source_url = models.URLField(max_length=512, null=True, blank=True,
                                 help_text="URL of the nutritional data source (e.g., USDA).")

    # --- Timestamps ---
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']  # Good practice to have a default order

    def __str__(self):
        return self.name


############################### ----------------------------Foood Table End_---------------------################################
# Strict mass/volume units — convert directly to grams (1 ml ≈ 1 g water-density assumption)
MASS_UNIT_TO_GRAMS = {
    "g": 1.0, "gram": 1.0,
    "kg": 1000.0, "kilogram": 1000.0,
    "mg": 0.001, "milligram": 0.001,
    "milliliters": 1.0, "ml": 1.0,
    "liters": 1000.0, "liter": 1000.0, "l": 1000.0,
}

# Serving/household units — approximate grams per 1 unit
# food_item.gram_equivalent overrides these when the FoodItem has a known serving weight
SERVING_UNIT_TO_GRAMS = {
    "cup": 240.0,
    "glass": 350.0,     # tall glass ≈ 350 ml
    "bowl": 300.0,
    "plate": 350.0,
    "piece": 100.0,
    "slice": 30.0,
    "tbsp": 15.0,
    "tablespoon": 15.0,
    "tsp": 5.0,
    "teaspoon": 5.0,
    "handful": 30.0,
    "pinch": 0.5,
    "dash": 1.0,
    "sprinkle": 2.0,
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

    PORTION_CHOICES = [
        ("Small", "Small"),
        ("Medium", "Medium"),
        ("Large", "Large"),
    ]
    PORTION_MULTIPLIERS = {"Small": 0.75, "Medium": 1.0, "Large": 1.5}

    # --- These Core Fields must be exactly the same ---
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    food_item = models.ForeignKey(
        'FoodItem', on_delete=models.SET_NULL, null=True, blank=True)
    food_name = models.CharField(max_length=150, blank=True, null=True)

    quantity = models.FloatField()
    unit = models.CharField(
        max_length=20, choices=UNIT_CHOICES, default="Gram")
    portion_size = models.CharField(
        max_length=10, choices=PORTION_CHOICES, default="Medium", blank=True)
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
        """Calculates nutrients snapshot, factoring:
        - quantity + unit conversion
        - portion_size multiplier
        - selected UserMealAttribute nutrition multipliers (if any)
        """
        if not self.food_item:
            return

        food_item = self.food_item
        user_quantity = self.quantity
        user_unit_lower = (self.unit or "").lower()
        portion_multiplier = self.PORTION_MULTIPLIERS.get(self.portion_size, 1.0)

        base_grams = (
            food_item.gram_equivalent
            if (food_item.gram_equivalent and food_item.gram_equivalent > 0)
            else (food_item.default_quantity or 100.0)
        )
        base_grams = float(base_grams) if base_grams else 100.0

        factor = 1.0
        if user_unit_lower in MASS_UNIT_TO_GRAMS:
            logged_grams = user_quantity * MASS_UNIT_TO_GRAMS[user_unit_lower]
            factor = (logged_grams / base_grams) * portion_multiplier

        elif user_unit_lower in SERVING_UNIT_TO_GRAMS:
            unit_grams = SERVING_UNIT_TO_GRAMS[user_unit_lower]
            logged_grams = user_quantity * unit_grams
            factor = (logged_grams / base_grams) * portion_multiplier

        else:
            factor = user_quantity * portion_multiplier

        # Apply attribute nutrition multipliers (backward compatible)
        attribute_multiplier = 1.0
        # DEBUG/TRACE: identify attribute multipliers applied
        debug_lines = []
        try:
            selected = self.meal_attributes.select_related('selected_option').all()
            if selected.exists():
                attribute_multiplier = 1.0
                for ma in selected:
                    m = getattr(ma.selected_option, 'nutrition_multiplier', 1.0) if ma.selected_option_id else 1.0
                    try:
                        m_float = float(m)
                    except (TypeError, ValueError):
                        m_float = 1.0
                    attribute_multiplier *= m_float

                    # Trace per attribute
                    try:
                        debug_lines.append(
                            f"attr={ma.attribute.name if ma.attribute_id else None} opt={ma.selected_option.value if ma.selected_option_id else None} mult={m_float}"
                        )
                    except Exception:
                        debug_lines.append("attr_mult_trace=unavailable")
        except Exception:
            attribute_multiplier = 1.0

        # Extra trace for the Size attribute (if present)
        try:
            size_attr = next((ma for ma in getattr(self, 'meal_attributes', []).all() if getattr(ma.attribute, 'name', None) == 'Size'), None)
            size_value = size_attr.selected_option.value if size_attr and size_attr.selected_option_id else None
            size_mult = size_attr.selected_option.nutrition_multiplier if size_attr and size_attr.selected_option_id else None
            debug_lines.append(f"SIZE_SELECTED={size_value} SIZE_MULT={size_mult}")
        except Exception:
            debug_lines.append("SIZE_TRACE=unavailable")

        # Apply attribute multipliers
        factor_before = factor
        factor = factor * attribute_multiplier

        # Debug output: only via logger (no stdout)
        try:
            logger = logging.getLogger(__name__)
            logger.info(
                "UserMeal attr nutrition calc: meal_id=%s food=%s portion_size=%s factor_before=%s attr_multiplier=%s factor_after=%s traces=[%s]",
                self.id,
                getattr(food_item, 'name', None),
                self.portion_size,
                factor_before,
                attribute_multiplier,
                factor,
                " | ".join(debug_lines)[:1500],
            )
        except Exception:
            pass


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


############################# ------- FOOD ATTRIBUTES SYSTEM -------#############################
# This system enables scalable support for foods that require additional attributes
# Examples: Chapati (flour_type + size), Milk (fat_type), Rice (bowl_size), Tea (sugar_level)
# The system is completely generic and can handle any food and any attribute.


class FoodAttribute(models.Model):
    """
    Master table that defines what attributes a food can have.

    Examples:
    - Attribute name: "Flour Type" (for breads)
    - Attribute name: "Fat Type" (for milk/dairy)
    - Attribute name: "Sugar Level" (for tea/beverages)
    - Attribute name: "Size" (for various foods)

    This is shared across all foods - no need to create duplicate attributes.
    """
    name = models.CharField(max_length=100, unique=True,
                            help_text="e.g., 'Flour Type', 'Fat Type', 'Size'")
    description = models.TextField(
        blank=True, null=True, help_text="What this attribute represents")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class FoodAttributeOption(models.Model):
    """
    Defines the possible values/options for each attribute.

    Examples for "Flour Type":
    - Wheat
    - Bajra
    - Jowar
    - Multigrain

    Examples for "Fat Type" (Milk):
    - Toned
    - Double Toned
    - Full Cream

    By design, different foods can share the same option values.
    For example, both "Chapati" and "Bread" might use "Wheat" as an option.
    """
    attribute = models.ForeignKey(
        FoodAttribute, on_delete=models.CASCADE, related_name='options')
    value = models.CharField(
        max_length=100, help_text="The option value (e.g., 'Wheat', 'Toned')")
    display_name = models.CharField(
        max_length=100, default="", blank=True, help_text="Human-readable display name (optional)")
    description = models.TextField(blank=True, null=True)

    # Optional: nutritional adjustment factor for this option
    # Use 1.0 as default (no change). Use < 1.0 for lower nutritional value, > 1.0 for higher.
    # Example: "Double Toned" milk might have 0.95x the nutrition of standard milk
    nutrition_multiplier = models.FloatField(
        default=1.0, help_text="Nutritional adjustment factor (1.0 = no change)")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Can't have duplicate values for the same attribute
        unique_together = ('attribute', 'value')
        ordering = ['attribute__name', 'value']

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"


class FoodItemAttribute(models.Model):
    """
    Links a FoodItem to its required/optional attributes.

    This is the M2M relation that tells us:
    "Chapati supports Flour Type attribute"
    "Milk supports Fat Type attribute"

    An attribute can be marked as required to enforce that users must select it
    when logging that food. Optional attributes can be skipped.
    """
    food_item = models.ForeignKey(
        FoodItem, on_delete=models.CASCADE, related_name='attributes')
    attribute = models.ForeignKey(FoodAttribute, on_delete=models.CASCADE)

    is_required = models.BooleanField(
        default=True, help_text="If True, user must select this attribute when logging this food")

    # Ordering for UI display
    order = models.PositiveIntegerField(
        default=0, help_text="Display order in UI")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Each food can have each attribute only once
        unique_together = ('food_item', 'attribute')
        ordering = ['order', 'attribute__name']

    def __str__(self):
        return f"{self.food_item.name} -> {self.attribute.name}"


class UserMealAttribute(models.Model):
    """
    Stores the actual attribute values selected by the user for a specific meal.

    Example:
    User logs "Chapati" and selects:
    - Flour Type: "Wheat"
    - Size: "Medium"

    This table stores those selections linked to the UserMeal record.

    This enables:
    1. Proper nutrition calculation (based on selected attributes)
    2. Meal history with attribute context
    3. Pattern analysis (which attributes do users prefer?)
    """
    user_meal = models.ForeignKey(
        UserMeal, on_delete=models.CASCADE, related_name='meal_attributes')
    attribute = models.ForeignKey(FoodAttribute, on_delete=models.CASCADE)
    selected_option = models.ForeignKey(
        FoodAttributeOption, on_delete=models.PROTECT, help_text="The user's selected option for this attribute")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # One value per attribute per meal
        unique_together = ('user_meal', 'attribute')
        ordering = ['attribute__name']

    def __str__(self):
        return f"{self.user_meal.id}: {self.attribute.name} = {self.selected_option.value}"
