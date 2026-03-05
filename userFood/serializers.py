from rest_framework import serializers
from .models import Allergen, FoodType, MealType, UserMeal,FoodItem



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
    food_name_display = serializers.CharField(source='food_name', read_only=True)
    
    # For INPUT, we need a write-only field to accept the user's food name search query.
    food_name_input = serializers.CharField(write_only=True, required=True, source='food_name')
    
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
            "meal_type",
            "remarks",
            "consumed_at",
            "date",
            "calories", "protein", "carbs", "fats", "sugar", "fiber",
            "estimated_gi", "glycemic_load", "food_type",
            "gram_equivalent", 

            # Field for INPUT (what the user sends)
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