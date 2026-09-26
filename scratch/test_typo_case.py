import os
import django
import sys
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

# Setup Django environment
sys.path.insert(0, '/home/shivam-likhar/Desktop/Projects/trackintake/production/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from userFood.models import FoodItem, UserMeal
from subscriptions.models import Plan, UserSubscription
from userProfile.models import UserProfile

User = get_user_model()

def test_typo_handling():
    print("=" * 60)
    print("TESTING TYPO HANDLING: 'paniir masala' -> 'Paneer Masala'")
    print("=" * 60)

    # 1. Setup Test User
    user, _ = User.objects.get_or_create(
        email="typotest@example.com",
        defaults={"is_active": True}
    )
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.date_of_birth = date(1995, 1, 1)
    profile.height_cm = 175.0
    profile.weight_kg = 70.0
    profile.gender = "male"
    profile.activity_level = "Moderately Active"
    profile.goal = "Maintain Weight"
    profile.save()

    plan, _ = Plan.objects.get_or_create(
        name="Typo Test Plan",
        defaults={"price": 499, "duration_days": 365, "meal_log_allowed": True, "is_active": True}
    )
    plan.meal_log_allowed = True
    plan.save()

    UserSubscription.objects.filter(user=user).delete()
    UserSubscription.objects.create(
        user=user,
        plan=plan,
        start_date=timezone.now().date(),
        end_date=timezone.now().date() + timedelta(days=365),
        is_active=True
    )

    client = APIClient()
    client.force_authenticate(user=user)

    # Clear prior meals
    UserMeal.objects.filter(user=user).delete()

    # 2. Existing "Paneer Masala" in FoodItem table
    original_paneer_masala, _ = FoodItem.objects.update_or_create(
        name="Paneer Masala",
        defaults={
            "calories": 320.0,
            "protein": 12.0,
            "carbs": 10.0,
            "fats": 25.0,
            "default_quantity": 1.0,
            "default_unit": "Bowl",
            "gram_equivalent": 200.0,
            "is_verified": True,
        }
    )
    initial_id = original_paneer_masala.id
    initial_calories = original_paneer_masala.calories
    initial_count = FoodItem.objects.count()

    print(f"Baseline: 'Paneer Masala' (ID: {initial_id}) exists with {initial_calories} kcal.")
    print(f"Total FoodItems in DB before test: {initial_count}")

    # 3. Simulate user submitting a typo: 'paniir masala'
    # Mock Gemini API response returning canonical "Paneer Masala"
    mock_gemini_json = """{
      "food_item": {
        "name": "Paneer Masala",
        "default_quantity": 1,
        "default_unit": "Bowl",
        "gram_equivalent": 200,
        "calories": 999.0,
        "protein": 99.0,
        "carbs": 99.0,
        "fats": 99.0
      }
    }"""
    mock_response = MagicMock()
    mock_response.text = mock_gemini_json

    with patch('utils.gemini.client.models.generate_content', return_value=mock_response) as mock_gemini:
        print("\nLogging meal with typo: 'paniir masala' (1 Bowl)...")
        res = client.post(
            '/api/logmeals/',
            {"food_name": "paniir masala", "quantity": 1, "unit": "Bowl", "meal_type": "Lunch"},
            format='json'
        )

        assert res.status_code == status.HTTP_201_CREATED, f"Failed create: {res.data}"
        assert mock_gemini.called, "Gemini was NOT called for unrecognized typo!"
        print("  [PASS] 1. Gemini was invoked to resolve the unrecognized food name 'paniir masala'.")

    # 4. Verification of FoodItem table
    final_count = FoodItem.objects.count()
    assert final_count == initial_count, f"FoodItem count changed! Was {initial_count}, now {final_count}."
    print(f"  [PASS] 2. FoodItem table count is 100% UNCHANGED ({final_count} items). No duplicate row created.")

    reloaded_item = FoodItem.objects.get(id=initial_id)
    assert reloaded_item.calories == initial_calories, f"Existing FoodItem was mutated! Calories: {reloaded_item.calories}"
    assert reloaded_item.name == "Paneer Masala"
    print(f"  [PASS] 3. Existing FoodItem row was NOT updated or overwritten (calories remain {reloaded_item.calories} kcal, NOT Gemini's 999.0).")

    # 5. Verification of logged UserMeal
    logged_meal = UserMeal.objects.filter(user=user).latest('consumed_at')
    assert logged_meal.food_item_id == initial_id, f"Meal linked to wrong item: {logged_meal.food_item_id}"
    assert logged_meal.food_name == "Paneer Masala", f"Meal has wrong display name: {logged_meal.food_name}"
    # 1 Bowl = 150g. Base = 200g = 320 kcal. 150/200 * 320 = 240.0 kcal.
    assert logged_meal.calories == 240.0, f"Expected 240.0 kcal, got {logged_meal.calories}"
    assert logged_meal.protein == 9.0, f"Expected 9.0g protein, got {logged_meal.protein}"
    print(f"  [PASS] 4. UserMeal displays corrected name '{logged_meal.food_name}', linked to existing FoodItem (ID {logged_meal.food_item_id}).")
    print(f"  [PASS] 5. Nutrition accurately calculated from existing FoodItem: {logged_meal.calories} kcal, {logged_meal.protein}g protein.")

    print("\n" + "=" * 60)
    print("ALL TYPO RESOLUTION & TABLE IMMUTABILITY CHECKS PASSED 100%!")
    print("=" * 60)

if __name__ == '__main__':
    test_typo_handling()
