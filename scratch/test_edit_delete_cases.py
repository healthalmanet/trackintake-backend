import os
import django
import sys
from datetime import date, datetime, time

# Setup Django environment
sys.path.insert(0, '/home/shivam-likhar/Desktop/Projects/trackintake/production/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from datetime import timedelta
from userFood.models import FoodItem, UserMeal
from subscriptions.models import Plan, UserSubscription

User = get_user_model()

def run_tests():
    print("=" * 60)
    print("RUNNING THOROUGH MEAL EDIT & DELETE TEST SUITE")
    print("=" * 60)

    # 1. Setup Test Users
    user1, _ = User.objects.get_or_create(
        email="edittestuser1@example.com",
        defaults={"is_active": True}
    )
    user2, _ = User.objects.get_or_create(
        email="edittestuser2@example.com",
        defaults={"is_active": True}
    )

    # Ensure paid plan with meal logging allowed
    plan, _ = Plan.objects.get_or_create(
        name="Premium Test Plan",
        defaults={
            "price": 499,
            "duration_days": 365,
            "meal_log_allowed": True,
            "is_active": True,
        }
    )
    plan.price = 499
    plan.meal_log_allowed = True
    plan.save()

    # Ensure active subscriptions and UserProfile for test users
    from userProfile.models import UserProfile
    for u in [user1, user2]:
        profile, _ = UserProfile.objects.get_or_create(user=u)
        profile.date_of_birth = date(1995, 1, 1)
        profile.height_cm = 175.0
        profile.weight_kg = 70.0
        profile.gender = "male"
        profile.activity_level = "Moderately Active"
        profile.goal = "Maintain Weight"
        profile.save()
        UserSubscription.objects.filter(user=u).delete()
        UserSubscription.objects.create(
            user=u,
            plan=plan,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=365),
            is_active=True
        )

    client1 = APIClient()
    client1.force_authenticate(user=user1)

    client2 = APIClient()
    client2.force_authenticate(user=user2)

    # Clear prior test meals for these test users
    UserMeal.objects.filter(user__in=[user1, user2]).delete()

    # Ensure baseline food items exist
    rice_food, _ = FoodItem.objects.get_or_create(
        name="Rice",
        defaults={
            "calories": 130.0,
            "protein": 2.7,
            "carbs": 28.0,
            "fats": 0.3,
            "default_quantity": 100.0,
            "default_unit": "Gram",
            "gram_equivalent": 100.0,
            "is_verified": True,
        }
    )
    paneer_masala_food, _ = FoodItem.objects.get_or_create(
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

    initial_food_count = FoodItem.objects.count()

    # =========================================================================
    # TEST CASE 1: Create Initial Meal (1 Bowl Rice = 150g -> 195.0 kcal)
    # =========================================================================
    print("\n--- TEST CASE 1: Create Baseline Meal (1 Bowl Rice) ---")
    create_response = client1.post(
        '/api/logmeals/',
        {"food_name": "Rice", "quantity": 1, "unit": "Bowl", "meal_type": "Lunch"},
        format='json'
    )
    assert create_response.status_code == status.HTTP_201_CREATED, f"Failed create: {create_response.data}"
    meal_id = create_response.data["data"][0]["id"]
    meal = UserMeal.objects.get(id=meal_id)
    assert meal.calories == 195.0, f"Expected 195.0 kcal, got {meal.calories}"
    print(f"  [PASS] Created Meal ID {meal_id}: 1 Bowl Rice = {meal.calories} kcal")

    # =========================================================================
    # TEST CASE 2: Edit Quantity (1 Bowl -> 2 Bowls -> 390.0 kcal)
    # =========================================================================
    print("\n--- TEST CASE 2: Edit Quantity (1 Bowl -> 2 Bowls) ---")
    patch_response = client1.patch(
        f'/api/logmeals/{meal_id}/',
        {"quantity": 2},
        format='json'
    )
    assert patch_response.status_code == status.HTTP_200_OK, f"Failed patch: {patch_response.data}"
    
    meal.refresh_from_db()
    assert meal.quantity == 2.0, f"Expected quantity 2.0, got {meal.quantity}"
    assert meal.calories == 390.0, f"Expected 390.0 kcal (2*150g/100g*130), got {meal.calories}"
    assert round(meal.protein, 2) == 8.1, f"Expected 8.1g protein (2.7*3), got {meal.protein}"
    print(f"  [PASS] Quantity updated to 2 Bowls: calories = {meal.calories} kcal, protein = {meal.protein}g")

    # =========================================================================
    # TEST CASE 3: Edit Unit (Bowl -> Plate: 350g -> 455.0 kcal)
    # =========================================================================
    print("\n--- TEST CASE 3: Edit Unit (2 Bowls -> 1 Plate) ---")
    patch_response = client1.patch(
        f'/api/logmeals/{meal_id}/',
        {"quantity": 1, "unit": "Plate"},
        format='json'
    )
    assert patch_response.status_code == status.HTTP_200_OK, f"Failed patch: {patch_response.data}"

    meal.refresh_from_db()
    assert meal.unit == "Plate", f"Expected unit 'Plate', got {meal.unit}"
    # 1 Plate = 350g. Factor = 350/100 = 3.5. 130 * 3.5 = 455.0 kcal
    assert meal.calories == 455.0, f"Expected 455.0 kcal, got {meal.calories}"
    print(f"  [PASS] Unit updated to 1 Plate: calories = {meal.calories} kcal (350g)")

    # =========================================================================
    # TEST CASE 4: Edit with exact_grams override (1 Plate -> exact_grams = 100g)
    # =========================================================================
    print("\n--- TEST CASE 4: Edit with exact_grams override (100g) ---")
    patch_response = client1.patch(
        f'/api/logmeals/{meal_id}/',
        {"exact_grams": 100},
        format='json'
    )
    assert patch_response.status_code == status.HTTP_200_OK, f"Failed patch: {patch_response.data}"

    meal.refresh_from_db()
    assert meal.quantity == 100.0, f"Expected quantity 100.0, got {meal.quantity}"
    assert meal.unit == "Gram", f"Expected unit 'Gram', got {meal.unit}"
    assert meal.calories == 130.0, f"Expected 130.0 kcal, got {meal.calories}"
    print(f"  [PASS] exact_grams override applied: {meal.quantity} {meal.unit} = {meal.calories} kcal")

    # =========================================================================
    # TEST CASE 5: Edit Food (Change Rice to Paneer Masala)
    # =========================================================================
    print("\n--- TEST CASE 5: Edit Food (Rice -> Paneer Masala, 1 Bowl = 150g) ---")
    patch_response = client1.patch(
        f'/api/logmeals/{meal_id}/',
        {"food_name": "Paneer Masala", "quantity": 1, "unit": "Bowl"},
        format='json'
    )
    assert patch_response.status_code == status.HTTP_200_OK, f"Failed patch: {patch_response.data}"

    meal.refresh_from_db()
    assert meal.food_item.name == "Paneer Masala"
    assert meal.food_name == "Paneer Masala"
    # Paneer Masala base: 200g = 320 kcal. 1 Bowl = 150g -> factor 0.75 -> 240.0 kcal
    assert meal.calories == 240.0, f"Expected 240.0 kcal, got {meal.calories}"
    assert meal.protein == 9.0, f"Expected 9.0g protein, got {meal.protein}"
    print(f"  [PASS] Food changed to Paneer Masala: calories = {meal.calories} kcal, protein = {meal.protein}g")

    # =========================================================================
    # TEST CASE 6: Edit Meal Type and Remarks (Metadata only, calories intact)
    # =========================================================================
    print("\n--- TEST CASE 6: Edit Meal Type & Remarks ---")
    patch_response = client1.patch(
        f'/api/logmeals/{meal_id}/',
        {"meal_type": "Dinner", "remarks": "Low salt preparation"},
        format='json'
    )
    assert patch_response.status_code == status.HTTP_200_OK

    meal.refresh_from_db()
    assert meal.meal_type == "Dinner"
    assert meal.remarks == "Low salt preparation"
    assert meal.calories == 240.0
    print(f"  [PASS] Metadata updated: meal_type='{meal.meal_type}', remarks='{meal.remarks}', calories unchanged ({meal.calories} kcal)")

    # =========================================================================
    # TEST CASE 7: Security Isolation (User 2 cannot edit or delete User 1's meal)
    # =========================================================================
    print("\n--- TEST CASE 7: Multi-User Security Isolation ---")
    user2_patch = client2.patch(
        f'/api/logmeals/{meal_id}/',
        {"quantity": 10},
        format='json'
    )
    assert user2_patch.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN]
    print(f"  [PASS] User 2 cannot edit User 1's meal (HTTP {user2_patch.status_code})")

    user2_del = client2.delete(f'/api/logmeals/{meal_id}/')
    assert user2_del.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN]
    print(f"  [PASS] User 2 cannot delete User 1's meal (HTTP {user2_del.status_code})")

    # =========================================================================
    # TEST CASE 8: Delete Meal (HTTP 204 No Content & Database Removal)
    # =========================================================================
    print("\n--- TEST CASE 8: Delete Meal by Owner ---")
    del_response = client1.delete(f'/api/logmeals/{meal_id}/')
    assert del_response.status_code == status.HTTP_204_NO_CONTENT, f"Expected 204, got {del_response.status_code}"

    # Verify meal no longer exists in DB
    assert not UserMeal.objects.filter(id=meal_id).exists()
    print(f"  [PASS] Meal ID {meal_id} successfully deleted from database (HTTP 204).")

    # =========================================================================
    # TEST CASE 9: Immutability of FoodItem Table
    # =========================================================================
    print("\n--- TEST CASE 9: FoodItem Table Immutability ---")
    final_food_count = FoodItem.objects.count()
    assert final_food_count == initial_food_count, f"Food count changed from {initial_food_count} to {final_food_count}!"
    print(f"  [PASS] FoodItem table unchanged ({final_food_count} items before and after).")

    print("\n" + "=" * 60)
    print("ALL EDIT & DELETE TESTS PASSED WITH 100% ACCURACY!")
    print("=" * 60)

if __name__ == '__main__':
    run_tests()
