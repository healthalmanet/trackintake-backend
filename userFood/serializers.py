from rest_framework import serializers
from .models import (
    Allergen, FoodType, MealType, UserMeal, FoodItem,
    FoodAttribute, FoodAttributeOption, FoodItemAttribute, UserMealAttribute
)


class FoodTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodType
        fields = ['id', 'name']


class MealTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealType
        fields = ['id', 'name']


class AllergenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Allergen
        fields = ['id', 'name']


# --- Main Serializer ---
class FoodItemSerializer2(serializers.ModelSerializer):
    # This is the key part: Use the nested serializers
    food_types = FoodTypeSerializer(many=True, read_only=True)
    meal_types = MealTypeSerializer(many=True, read_only=True)
    allergens = AllergenSerializer(many=True, read_only=True)

    class Meta:
        model = FoodItem
        # IMPORTANT: Make sure the names 'food_types', 'meal_types', 'allergens'
        # are included in this list!
        fields = [
            'id', 'name', 'default_quantity', 'default_unit', 'gram_equivalent',
            'calories', 'protein', 'carbs', 'fats', 'sugar', 'fiber',
            'saturated_fat_g', 'trans_fat_g', 'estimated_gi', 'glycemic_load',
            'sodium_mg', 'potassium_mg', 'iron_mg', 'calcium_mg', 'iodine_mcg',
            'zinc_mg', 'magnesium_mg', 'selenium_mcg', 'cholesterol_mg',
            'omega_3_g', 'vitamin_d_mcg', 'vitamin_b12_mcg', 'fodmap_level',
            'spice_level', 'purine_level', 'is_verified', 'source_url',
            'created_at', 'updated_at',
            # ------> VERIFY THESE ARE HERE <------
            'food_types',
            'meal_types',
            'allergens',
        ]


class UserMealSerializer(serializers.ModelSerializer):
    """
    A robust serializer for the UserMeal model that safely handles
    relationships and provides clear input/output fields.
    """
    food_name_display = serializers.CharField(source='food_name', read_only=True)
    food_name_input   = serializers.CharField(write_only=True, required=True, source='food_name')

    gram_equivalent  = serializers.SerializerMethodField()
    effective_grams  = serializers.SerializerMethodField()

    class Meta:
        model = UserMeal
        fields = [
            "id",
            "food_name_display",
            "quantity",
            "unit",
            "portion_size",
            "meal_type",
            "remarks",
            "consumed_at",
            "date",
            # Computed read-only
            "calories", "protein", "carbs", "fats", "sugar", "fiber",
            "estimated_gi", "glycemic_load", "food_type",
            "gram_equivalent",
            "effective_grams",
            # Input only
            "food_name_input",
        ]
        read_only_fields = [
            "id", "effective_grams", "calories", "protein", "carbs", "fats",
            "sugar", "fiber", "estimated_gi", "glycemic_load", "food_type",
            "gram_equivalent",
        ]

    def get_gram_equivalent(self, obj: UserMeal) -> float | None:
        """Safely gets the gram_equivalent from the related food_item."""
        return obj.food_item.gram_equivalent if obj.food_item else None

    def get_effective_grams(self, obj: UserMeal) -> float | None:
        """Returns how many grams were used in the nutrition calculation."""
        try:
            return round(obj._get_effective_grams(), 2)
        except Exception:
            return None

    def create(self, validated_data):
        return super().create(validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)


############################# ------- FOOD ATTRIBUTES SERIALIZERS -------#############################


class FoodAttributeOptionSerializer(serializers.ModelSerializer):
    """
    Serializer for attribute options (values).
    Example: "Wheat", "Bajra", "Jowar" for "Flour Type" attribute
    """
    class Meta:
        model = FoodAttributeOption
        fields = ['id', 'value', 'display_name',
                  'description', 'nutrition_multiplier']


class FoodAttributeSerializer(serializers.ModelSerializer):
    """
    Serializer for food attributes with their available options.

    Response format:
    {
        "id": 1,
        "name": "Flour Type",
        "description": "Type of flour used in the bread",
        "options": [
            {"id": 1, "value": "Wheat", "display_name": "Whole Wheat", "nutrition_multiplier": 1.0},
            {"id": 2, "value": "Bajra", "display_name": "Pearl Millet", "nutrition_multiplier": 1.05},
            ...
        ]
    }
    """
    options = FoodAttributeOptionSerializer(many=True, read_only=True)

    class Meta:
        model = FoodAttribute
        fields = ['id', 'name', 'description', 'options']


class FoodItemAttributeSerializer(serializers.ModelSerializer):
    """
    Serializer for FoodItem's attributes (tells which attributes a food requires).

    Used in the food details API response to show:
    "This food item requires these attributes"
    """
    attribute = FoodAttributeSerializer(read_only=True)
    attribute_id = serializers.PrimaryKeyRelatedField(
        queryset=FoodAttribute.objects.all(),
        source='attribute',
        write_only=True,
        required=False
    )

    class Meta:
        model = FoodItemAttribute
        fields = ['id', 'attribute', 'attribute_id', 'is_required', 'order']


class FoodItemWithAttributesSerializer(serializers.ModelSerializer):
    """
    Extended FoodItem serializer that includes its attributes.
    This is the main API response for fetching food details.

    Use this when fetching food details to show users what attributes they need to select.
    """
    food_types = FoodTypeSerializer(many=True, read_only=True)
    meal_types = MealTypeSerializer(many=True, read_only=True)
    allergens = AllergenSerializer(many=True, read_only=True)
    attributes = FoodItemAttributeSerializer(many=True, read_only=True)

    class Meta:
        model = FoodItem
        fields = [
            'id', 'name', 'default_quantity', 'default_unit', 'gram_equivalent',
            'calories', 'protein', 'carbs', 'fats', 'sugar', 'fiber',
            'saturated_fat_g', 'trans_fat_g', 'estimated_gi', 'glycemic_load',
            'sodium_mg', 'potassium_mg', 'iron_mg', 'calcium_mg', 'iodine_mcg',
            'zinc_mg', 'magnesium_mg', 'selenium_mcg', 'cholesterol_mg',
            'omega_3_g', 'vitamin_d_mcg', 'vitamin_b12_mcg', 'fodmap_level',
            'spice_level', 'purine_level', 'is_verified', 'source_url',
            'created_at', 'updated_at',
            'food_types', 'meal_types', 'allergens',
            'attributes',  # NEW: Include attributes
        ]


class UserMealAttributeSerializer(serializers.ModelSerializer):
    """
    Serializer for the attribute values selected by a user for a specific meal.

    Response format:
    {
        "id": 123,
        "attribute_id": 1,
        "attribute_name": "Flour Type",
        "selected_option_id": 2,
        "selected_option_value": "Bajra",
        "nutrition_multiplier": 1.05
    }
    """
    attribute_id = serializers.SerializerMethodField()
    attribute_name = serializers.SerializerMethodField()
    selected_option_id = serializers.SerializerMethodField()
    selected_option_value = serializers.SerializerMethodField()
    nutrition_multiplier = serializers.SerializerMethodField()

    class Meta:
        model = UserMealAttribute
        fields = [
            'id',
            'attribute_id', 'attribute_name',
            'selected_option_id', 'selected_option_value',
            'nutrition_multiplier'
        ]

    def get_attribute_id(self, obj):
        return obj.attribute.id

    def get_attribute_name(self, obj):
        return obj.attribute.name

    def get_selected_option_id(self, obj):
        return obj.selected_option.id

    def get_selected_option_value(self, obj):
        return obj.selected_option.value

    def get_nutrition_multiplier(self, obj):
        return obj.selected_option.nutrition_multiplier


class UserMealWithAttributesSerializer(serializers.ModelSerializer):
    """Extended UserMeal serializer — includes exact overrides and effective_grams."""
    food_name_display = serializers.CharField(source='food_name', read_only=True)
    food_name_input   = serializers.CharField(write_only=True, required=True, source='food_name')
    gram_equivalent   = serializers.SerializerMethodField()
    effective_grams   = serializers.SerializerMethodField()

    class Meta:
        model = UserMeal
        fields = [
            "id",
            "food_name_display",
            "quantity",
            "unit",
            "portion_size",
            "meal_type",
            "remarks",
            "consumed_at",
            "date",
            "calories", "protein", "carbs", "fats", "sugar", "fiber",
            "estimated_gi", "glycemic_load", "food_type",
            "gram_equivalent",
            "effective_grams",
            "food_name_input",
        ]
        read_only_fields = [
            "id", "calories", "protein", "carbs", "fats",
            "sugar", "fiber", "estimated_gi", "glycemic_load", "food_type",
            "gram_equivalent",
            "effective_grams",
        ]

    def get_gram_equivalent(self, obj: UserMeal) -> float | None:
        return obj.food_item.gram_equivalent if obj.food_item else None

    def get_effective_grams(self, obj: UserMeal) -> float | None:
        try:
            return round(obj._get_effective_grams(), 2)
        except Exception:
            return None
