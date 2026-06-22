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
    # Use 'source' for direct relationships, but ensure it's safe.
    # The 'food_name' on the UserMeal model itself is the source of truth for output.
    food_name_display = serializers.CharField(
        source='food_name', read_only=True)

    # For INPUT, we need a write-only field to accept the user's food name search query.
    food_name_input = serializers.CharField(
        write_only=True, required=True, source='food_name')

    # --- The Fix for gram_equivalent ---
    # Use a SerializerMethodField to safely access the related FoodItem's data.
    gram_equivalent = serializers.SerializerMethodField()

    class Meta:
        model = UserMeal
        fields = [
            "id",
            # Fields for OUTPUT (what the user sees)
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

            # Field for INPUT (what the user sends)
            "portion_size",
            "food_name_input",
        ]

        # All nutritional data is calculated by the model's save() method,
        # so these fields are correctly read-only from the API's perspective.
        read_only_fields = [
            "id", "calories", "protein", "carbs", "fats", "sugar",
            "fiber", "estimated_gi", "glycemic_load", "food_type",
            "gram_equivalent",
        ]

        # We don't need to specify 'user' as it's set in the view.
        # We don't need 'food_item_id' as the view handles it via 'food_name_input'.

    def get_gram_equivalent(self, obj: UserMeal) -> float | None:
        """
        Safely gets the gram_equivalent from the related food_item.
        Returns None if the food_item does not exist, preventing crashes.
        """
        if obj.food_item:
            return obj.food_item.gram_equivalent
        return None

    def create(self, validated_data):
        # The view now handles the creation logic, so this can be simplified.
        # However, it's good practice to handle it here if the view were simpler.
        # We will let the view's 'process_meal' function handle the logic.
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # The view also handles the update logic.
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
    """Extended UserMeal serializer that includes selected attributes."""
    food_name_display = serializers.CharField(source='food_name', read_only=True)
    food_name_input = serializers.CharField(write_only=True, required=True, source='food_name')
    gram_equivalent = serializers.SerializerMethodField()
    meal_attributes = UserMealAttributeSerializer(many=True, read_only=True)

    # Optional normalized fields for UI/backward compatibility
    # (derived from meal_attributes; do not change stored contract)
    selected_size = serializers.SerializerMethodField()
    flour_type = serializers.SerializerMethodField()

    class Meta:
        model = UserMeal
        fields = [
            "id",
            "food_name_display",
            "quantity",
            "unit",
            "portion_size",
            "selected_size",
            "meal_type",
            "remarks",
            "consumed_at",
            "date",
            "calories", "protein", "carbs", "fats", "sugar", "fiber",
            "estimated_gi", "glycemic_load", "food_type",
            "gram_equivalent",
            "meal_attributes",
            "flour_type",
            "food_name_input",
        ]


        read_only_fields = [
            "id", "calories", "protein", "carbs", "fats", "sugar",
            "fiber", "estimated_gi", "glycemic_load", "food_type",
            "gram_equivalent", "meal_attributes",
        ]

    def get_gram_equivalent(self, obj: UserMeal) -> float | None:
        if obj.food_item:
            return obj.food_item.gram_equivalent
        return None

    def _get_attr_value_by_name(self, obj: UserMeal, attr_name: str):
        try:
            for ma in getattr(obj, 'meal_attributes', []).all() if hasattr(getattr(obj, 'meal_attributes', None), 'all') else getattr(obj, 'meal_attributes', []):
                if getattr(ma.attribute, 'name', None) == attr_name:
                    return getattr(ma.selected_option, 'value', None)
        except Exception:
            pass
        return None

    def get_selected_size(self, obj: UserMeal):
        # If your UI expects {portion_size: "Medium"} this will still be driven by stored field.
        # This field helps when UI reads attribute 'Size'.
        return self._get_attr_value_by_name(obj, 'Size')

    def get_flour_type(self, obj: UserMeal):
        return self._get_attr_value_by_name(obj, 'Flour Type')

