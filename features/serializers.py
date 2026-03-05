
from rest_framework import serializers

from user.models import User
from .models import WeightLog, WaterIntakeLog, CustomReminder, Message, Blog
from userFood.models import Allergen, FoodItem, FoodType, MealType
from django.utils import timezone
from datetime import datetime, timedelta

class WeightLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeightLog
        fields = ['id', 'date', 'weight_kg', 'time_logged']
        read_only_fields = ['time_logged']



class WaterIntakeLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WaterIntakeLog
        fields = '__all__'
        read_only_fields = ('user', 'date')





class CustomReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomReminder
        fields = [
            'id', 'title', 'description', 'reminder_time', 
            'frequency', 'is_active', 'next_due_at'
        ]
        read_only_fields = ['id', 'is_active', 'next_due_at']

    def create(self, validated_data):
        # Set the user from the request context provided by DRF
        validated_data['user'] = self.context['request'].user
        
        # --- Calculate the initial next_due_at ---
        reminder_time = validated_data['reminder_time']
        
        # Use the current time in the project's timezone (as set in settings.py)
        now = timezone.localtime(timezone.now())
        
        # Combine today's date with the user's desired time to create a "naive" datetime
        initial_due_datetime_naive = datetime.combine(now.date(), reminder_time)
        
        # Make the datetime "aware" of the project's timezone
        initial_next_due_at = timezone.make_aware(initial_due_datetime_naive)

        # If the calculated time is already in the past for today, schedule it for the next day
        if initial_next_due_at < now:
            initial_next_due_at += timedelta(days=1)
            
        validated_data['next_due_at'] = initial_next_due_at
        
        return super().create(validated_data)






#Forgot PassWord

class UserBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name', 'email']







class MessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.IntegerField(source='sender.id', read_only=True)
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    sender_email = serializers.EmailField(source='sender.email', read_only=True)

    receiver_id = serializers.IntegerField(source='receiver.id', read_only=True)
    receiver_name = serializers.CharField(source='receiver.full_name', read_only=True)
    receiver_email = serializers.EmailField(source='receiver.email', read_only=True)

    class Meta:
        model = Message
        fields = [
            'id',
            'sender_id', 'sender_name', 'sender_email',
            'receiver_id', 'receiver_name', 'receiver_email',
            'text',
            'timestamp',
            'is_read'
        ]





class BlogSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.full_name', read_only=True)

    class Meta:
        model = Blog
        fields = [
            'id', 'author', 'author_name',
            'title', 'content',
            'image',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'author', 'created_at', 'updated_at']

    def validate(self, data):
        image = data.get('image')
        image_url = data.get('image_url')

        if not image and not image_url:
            raise serializers.ValidationError("You must provide either an image file or an image URL.")
        
        return data
    

class FoodTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodType
        fields = ['id', 'name'] # Show both the ID and the name

class MealTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealType
        fields = ['id', 'name']

class AllergenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Allergen
        fields = ['id', 'name']


class FoodItemSerializer2(serializers.ModelSerializer):
    # --- THIS IS THE KEY CHANGE ---
    # Tell DRF to use the serializers we created above for these fields.
    # many=True is required for many-to-many relationships.
    # read_only=True is good practice for nested representations to prevent write ambiguity.
    food_types = FoodTypeSerializer(many=True, read_only=True)
    meal_types = MealTypeSerializer(many=True, read_only=True)
    allergens = AllergenSerializer(many=True, read_only=True)

    class Meta:
        model = FoodItem
        fields = [
            'id',
            'name',
            'default_quantity',
            'default_unit',
            'gram_equivalent',
            'calories',
            'protein',
            'carbs',
            'fats',
            'sugar',
            'fiber',
            'saturated_fat_g',
            'trans_fat_g',
            'estimated_gi',
            'glycemic_load',
            'sodium_mg',
            'potassium_mg',
            'iron_mg',
            'calcium_mg',
            'iodine_mcg',
            'zinc_mg',
            'magnesium_mg',
            'selenium_mcg',
            'cholesterol_mg',
            'omega_3_g',
            'vitamin_d_mcg',
            'vitamin_b12_mcg',
            'fodmap_level',
            'spice_level',
            'purine_level',
            'is_verified',
            'source_url',
            'created_at',
            'updated_at',
            # You must include the relationship fields in the list
            'food_types',
            'meal_types',
            'allergens',
        ]