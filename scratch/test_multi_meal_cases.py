import os
import django
import sys
from datetime import date, timedelta

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

def run_tests():
    print("=" * 60)
    print("RUNNING MULTIPLE MEAL ITEMS & ADD ANOTHER MEAL TEST SUITE")
    print("=" * 60)

    # 1. Setup Test User
    user, _ = User.objects.get_or_create(
        email="multimealuser@example.com",
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
        name="Multi Meal Plan",
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

    # Clear prior meals for this test user
    UserMeal.objects.filter(user=user).delete()

    # 2. Setup Baseline Food Items
    rice, _ = FoodItem.objects.update_or_create(
        name="Rice",
        defaults={
            "calories": 130.0, "protein": 2.7, "carbs": 28.0, "fats": 0.3,
            "default_quantity": 100.0, "default_unit": "Gram",
            "gram_equivalent": 100.0, "is_verified": True,
        }
    )
    dal, _ = FoodItem.objects.update_or_create(
        name="Yellow Dal",
        defaults={
            "calories": 120.0, "protein": 7.0, "carbs": 18.0, "fats": 2.5,
            "default_quantity": 100.0, "default_unit": "Gram",
            "gram_equivalent": 100.0, "is_verified": True,
        }
    )
    paneer, _ = FoodItem.objects.update_or_create(
        name="Paneer",
        defaults={
            "calories": 265.0, "protein": 18.3, "carbs": 1.2, "fats": 20.8,
            "default_quantity": 100.0, "default_unit": "Gram",
            "gram_equivalent": 100.0, "is_verified": True,
        }
    )

    initial_food_count = FoodItem.objects.count()

    # =========================================================================
    # TEST CASE 1: Batch Submission of Multiple Food Items (e.g. Lunch with 3 items)
    # 1. 1 Bowl Rice (150g / 100g * 130 = 195.0 kcal, 4.05g protein)
    # 2. 1 Small Bowl Yellow Dal (100g / 100g * 120 = 120.0 kcal, 7.0g protein)
    # 3. 50 Grams Paneer (50g / 100g * 265 = 132.5 kcal, 9.15g protein)
    # Total Lunch Calories = 195.0 + 120.0 + 132.5 = 447.5 kcal
    # Total Lunch Protein = 4.05 + 7.0 + 9.15 = 20.2g
    # =========================================================================
    print("\n--- TEST CASE 1: Batch Submission of Multiple Meal Items in 1 Request ---")
    multi_items_payload = [
        {"food_name": "Rice", "quantity": 1, "unit": "Bowl", "meal_type": "Lunch"},
        {"food_name": "Yellow Dal", "quantity": 1, "unit": "Small Bowl", "meal_type": "Lunch"},
        {"food_name": "Paneer", "quantity": 50, "unit": "Gram", "meal_type": "Lunch"},
    ]

    batch_response = client.post('/api/logmeals/', multi_items_payload, format='json')
    assert batch_response.status_code == status.HTTP_201_CREATED, f"Batch post failed: {batch_response.data}"

    logged_items = batch_response.data.get("data", [])
    assert len(logged_items) == 3, f"Expected 3 logged items, got {len(logged_items)}"

    rice_meal = next(m for m in logged_items if m["food_name_display"] == "Rice")
    dal_meal = next(m for m in logged_items if m["food_name_display"] == "Yellow Dal")
    paneer_meal = next(m for m in logged_items if m["food_name_display"] == "Paneer")

    assert rice_meal["calories"] == 195.0, f"Rice calories wrong: {rice_meal['calories']}"
    assert dal_meal["calories"] == 120.0, f"Dal calories wrong: {dal_meal['calories']}"
    assert paneer_meal["calories"] == 132.5, f"Paneer calories wrong: {paneer_meal['calories']}"

    totals = batch_response.data.get("totals", {})
    assert totals.get("total_calories") == 447.5, f"Expected 447.5 total calories, got {totals.get('total_calories')}"
    assert round(totals.get("total_protein"), 2) == 20.2, f"Expected 20.2g protein, got {totals.get('total_protein')}"
    print(f"  [PASS] Logged 3 items in batch: Rice (195.0 kcal) + Dal (120.0 kcal) + Paneer (132.5 kcal)")
    print(f"  [PASS] Aggregated totals returned by API: {totals['total_calories']} kcal, {totals['total_protein']}g protein")

    # =========================================================================
    # TEST CASE 2: Add Another Meal to the Same Day (e.g. Dinner after Lunch)
    # User adds 1 Plate Rice (350g = 455.0 kcal) for Dinner
    # New Daily Total Calories = 447.5 + 455.0 = 902.5 kcal
    # =========================================================================
    print("\n--- TEST CASE 2: Add Another Meal to Same Day (Dinner after Lunch) ---")
    dinner_payload = {
        "food_name": "Rice",
        "quantity": 1,
        "unit": "Plate",
        "meal_type": "Dinner"
    }

    dinner_response = client.post('/api/logmeals/', dinner_payload, format='json')
    assert dinner_response.status_code == status.HTTP_201_CREATED, f"Dinner post failed: {dinner_response.data}"

    updated_totals = dinner_response.data.get("totals", {})
    assert updated_totals.get("total_calories") == 902.5, f"Expected 902.5 kcal, got {updated_totals.get('total_calories')}"
    print(f"  [PASS] Added Dinner (1 Plate Rice = 455.0 kcal).")
    print(f"  [PASS] Daily total calories updated from 447.5 to {updated_totals['total_calories']} kcal.")

    # =========================================================================
    # TEST CASE 3: Add Another Food Item to an Existing Meal Type
    # User adds a 2nd Dinner item: 1 Bowl Yellow Dal (150g = 180.0 kcal)
    # New Daily Total Calories = 902.5 + 180.0 = 1082.5 kcal
    # =========================================================================
    print("\n--- TEST CASE 3: Add Another Food Item to Existing Meal Type ---")
    dinner_item_2 = {
        "food_name": "Yellow Dal",
        "quantity": 1,
        "unit": "Bowl",
        "meal_type": "Dinner"
    }

    d2_response = client.post('/api/logmeals/', dinner_item_2, format='json')
    assert d2_response.status_code == status.HTTP_201_CREATED

    d2_totals = d2_response.data.get("totals", {})
    assert d2_totals.get("total_calories") == 1082.5, f"Expected 1082.5 kcal, got {d2_totals.get('total_calories')}"
    print(f"  [PASS] Added Yellow Dal (1 Bowl = 180.0 kcal) to Dinner.")
    print(f"  [PASS] Daily total calories updated to {d2_totals['total_calories']} kcal.")

    # =========================================================================
    # TEST CASE 4: Verification via GET /api/logmeals/?date=today
    # Confirms query endpoint groups and returns all 5 meals logged across the day
    # =========================================================================
    print("\n--- TEST CASE 4: Retrieve All Logged Meals via GET Endpoint ---")
    today_str = timezone.now().date().isoformat()
    get_response = client.get(f'/api/logmeals/?date={today_str}')
    assert get_response.status_code == status.HTTP_200_OK

    results = get_response.data.get("results", []) if isinstance(get_response.data, dict) else get_response.data
    assert len(results) == 5, f"Expected 5 meals in query results, got {len(results)}"
    
    # Confirm meal types present
    meal_types = [m["meal_type"] for m in results]
    assert meal_types.count("Lunch") == 3
    assert meal_types.count("Dinner") == 2
    print(f"  [PASS] GET /api/logmeals/?date={today_str} returned 5 meals: 3 Lunch, 2 Dinner.")

    # =========================================================================
    # TEST CASE 5: Delete One of the Multiple Items
    # Delete the Yellow Dal from Dinner (180.0 kcal)
    # Remaining meals = 4, Total calories in DB = 1082.5 - 180.0 = 902.5 kcal
    # =========================================================================
    print("\n--- TEST CASE 5: Delete One Item from Multi-Meal Day ---")
    dal_dinner = UserMeal.objects.filter(user=user, meal_type="Dinner", food_name="Yellow Dal").first()
    assert dal_dinner is not None
    del_id = dal_dinner.id

    del_resp = client.delete(f'/api/logmeals/{del_id}/')
    assert del_resp.status_code == status.HTTP_204_NO_CONTENT

    remaining_meals = UserMeal.objects.filter(user=user)
    assert remaining_meals.count() == 4
    cal_sum = sum(m.calories for m in remaining_meals)
    assert cal_sum == 902.5
    print(f"  [PASS] Deleted Dinner Dal (ID {del_id}). Remaining 4 meals total exactly {cal_sum} kcal.")

    # =========================================================================
    # TEST CASE 6: FoodItem Table Immutability
    # =========================================================================
    print("\n--- TEST CASE 6: FoodItem Table Immutability Check ---")
    final_food_count = FoodItem.objects.count()
    assert final_food_count == initial_food_count
    print(f"  [PASS] FoodItem table unchanged ({final_food_count} rows before and after).")

    print("\n" + "=" * 60)
    print("ALL MULTI-ITEM & ADD ANOTHER MEAL TESTS PASSED 100%!")
    print("=" * 60)

if __name__ == '__main__':
    run_tests()
