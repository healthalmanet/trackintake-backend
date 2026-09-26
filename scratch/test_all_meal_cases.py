import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from django.contrib.auth import get_user_model
from userFood.models import FoodItem, UserMeal, SERVING_UNIT_TO_GRAMS
from userFood.views import UserMealViewSet, normalize_food_name, display_food_name

User = get_user_model()

def run_tests():
    print("=" * 60)
    print("RUNNING THOROUGH MEAL LOGGING TEST SUITE")
    print("=" * 60)

    # Setup test user (uses email, not username)
    user = User.objects.first()
    if not user:
        user = User.objects.create(email="test_meal_logger@example.com", is_active=True)

    # Cleanup any old test meals for this user
    UserMeal.objects.filter(user=user).delete()

    # -------------------------------------------------------------
    # SETUP TEST FOODS
    # -------------------------------------------------------------
    # 1. Plain Paneer: 100g = 265 kcal, 18.3g protein, 1.2g carbs, 20.8g fats
    paneer, _ = FoodItem.objects.update_or_create(
        name="Paneer",
        defaults={
            "default_quantity": 100,
            "default_unit": "Gram",
            "gram_equivalent": 100.0,
            "calories": 265.0,
            "protein": 18.3,
            "carbs": 1.2,
            "fats": 20.8,
            "is_verified": True,
        }
    )

    # 2. Paneer Masala: 200g serving = 320 kcal, 12.0g protein, 14.0g carbs, 24.0g fats
    paneer_masala, _ = FoodItem.objects.update_or_create(
        name="Paneer Masala",
        defaults={
            "default_quantity": 1,
            "default_unit": "Bowl",
            "gram_equivalent": 200.0,
            "calories": 320.0,
            "protein": 12.0,
            "carbs": 14.0,
            "fats": 24.0,
            "is_verified": True,
        }
    )

    # 3. White Rice: 100g = 130 kcal, 2.7g protein, 28.0g carbs, 0.3g fats
    rice, _ = FoodItem.objects.update_or_create(
        name="Rice",
        defaults={
            "default_quantity": 100,
            "default_unit": "Gram",
            "gram_equivalent": 100.0,
            "calories": 130.0,
            "protein": 2.7,
            "carbs": 28.0,
            "fats": 0.3,
            "is_verified": True,
        }
    )

    viewset = UserMealViewSet()

    # =============================================================
    # TEST CASE 1: Exact Normalized Matching & Collision Avoidance
    # =============================================================
    print("\n--- TEST CASE 1: Exact Food Matching (No False Collisions) ---")
    
    # 1a. "paneer" matches "Paneer"
    found = viewset._find_or_create_food_item("paneer", 100, "Gram")
    assert found.id == paneer.id, f"Expected Paneer (id {paneer.id}), got {found.name} (id {found.id})"
    print("  [PASS] 'paneer' matched 'Paneer' exactly.")

    # 1b. "  PANEER  " matches "Paneer"
    found = viewset._find_or_create_food_item("  PANEER  ", 100, "Gram")
    assert found.id == paneer.id, f"Expected Paneer, got {found.name}"
    print("  [PASS] '  PANEER  ' with uppercase and spaces matched 'Paneer'.")

    # 1c. "Paneer Masala" matches "Paneer Masala" (NOT Paneer!)
    found = viewset._find_or_create_food_item("Paneer Masala", 1, "Bowl")
    assert found.id == paneer_masala.id, f"Expected Paneer Masala (id {paneer_masala.id}), got {found.name}"
    print("  [PASS] 'Paneer Masala' matched 'Paneer Masala' (NOT confused with 'Paneer').")

    # 1d. "  paneer   masala  " matches "Paneer Masala"
    found = viewset._find_or_create_food_item("  paneer   masala  ", 1, "Bowl")
    assert found.id == paneer_masala.id, f"Expected Paneer Masala, got {found.name}"
    print("  [PASS] '  paneer   masala  ' matched 'Paneer Masala'.")

    # =============================================================
    # TEST CASE 2: Rice - 1 Bowl (default 150g) vs 100g base
    # =============================================================
    print("\n--- TEST CASE 2: 1 Bowl Rice (default 150g) vs 100g base ---")
    meal = UserMeal(
        user=user,
        food_item=rice,
        food_name="Rice",
        quantity=1.0,
        unit="Bowl"
    )
    meal.save()
    # Base: 100g = 130 kcal. 1 Bowl = 150g. Expected: 150/100 * 130 = 195 kcal
    assert meal.calories == 195.0, f"Expected 195.0 kcal, got {meal.calories}"
    assert meal.protein == round(2.7 * 1.5, 2), f"Expected {2.7 * 1.5}, got {meal.protein}"
    assert meal.carbs == round(28.0 * 1.5, 2), f"Expected {28.0 * 1.5}, got {meal.carbs}"
    assert meal.fats == round(0.3 * 1.5, 2), f"Expected {0.3 * 1.5}, got {meal.fats}"
    print(f"  [PASS] 1 Bowl Rice = {meal.calories} kcal (150g: factor 1.5).")

    # =============================================================
    # TEST CASE 3: Rice - User enters exact 100g (overriding Bowl default)
    # =============================================================
    print("\n--- TEST CASE 3: Exact 100g Override (User selected Bowl but entered 100g) ---")
    meal_exact = UserMeal(
        user=user,
        food_item=rice,
        food_name="Rice",
        quantity=100.0,
        unit="Gram"
    )
    meal_exact.save()
    # 100g / 100g = factor 1.0 -> 130 kcal
    assert meal_exact.calories == 130.0, f"Expected 130.0 kcal, got {meal_exact.calories}"
    assert meal_exact.protein == 2.7, f"Expected 2.7, got {meal_exact.protein}"
    assert meal_exact.carbs == 28.0, f"Expected 28.0, got {meal_exact.carbs}"
    print(f"  [PASS] Exact 100g Rice = {meal_exact.calories} kcal (factor 1.0).")

    # =============================================================
    # TEST CASE 4: Rice - User enters exact 150g directly in Grams
    # =============================================================
    print("\n--- TEST CASE 4: 150g Rice directly in Grams ---")
    meal_150g = UserMeal(
        user=user,
        food_item=rice,
        food_name="Rice",
        quantity=150.0,
        unit="Gram"
    )
    meal_150g.save()
    assert meal_150g.calories == 195.0, f"Expected 195.0 kcal, got {meal_150g.calories}"
    print(f"  [PASS] 150g Rice = {meal_150g.calories} kcal (factor 1.5).")

    # =============================================================
    # TEST CASE 5: All Household Unit Sizes Scaling Check
    # =============================================================
    print("\n--- TEST CASE 5: Household Unit Variations for Rice ---")
    unit_tests = [
        ("Small Bowl", 1.0, 100.0, 130.0),    # 100g -> factor 1.0 -> 130 kcal
        ("Bowl", 1.0, 150.0, 195.0),          # 150g -> factor 1.5 -> 195 kcal
        ("Big Bowl", 1.0, 250.0, 325.0),      # 250g -> factor 2.5 -> 325 kcal
        ("Small Plate", 1.0, 200.0, 260.0),   # 200g -> factor 2.0 -> 260 kcal
        ("Plate", 1.0, 350.0, 455.0),         # 350g -> factor 3.5 -> 455 kcal
        ("Big Plate", 1.0, 500.0, 650.0),     # 500g -> factor 5.0 -> 650 kcal
        ("Katori", 1.0, 150.0, 195.0),        # 150g -> factor 1.5 -> 195 kcal
        ("Vati", 1.0, 100.0, 130.0),          # 100g -> factor 1.0 -> 130 kcal
        ("Thali", 1.0, 400.0, 520.0),         # 400g -> factor 4.0 -> 520 kcal
    ]

    for unit_name, qty, expected_grams, expected_kcal in unit_tests:
        m = UserMeal(user=user, food_item=rice, food_name="Rice", quantity=qty, unit=unit_name)
        m.save()
        assert m.calories == expected_kcal, f"{unit_name}: Expected {expected_kcal} kcal, got {m.calories}"
        print(f"  [PASS] {qty} {unit_name} (~{expected_grams}g) -> {m.calories} kcal")

    # =============================================================
    # TEST CASE 6: Mass and Volume Units
    # =============================================================
    print("\n--- TEST CASE 6: Mass and Volume Conversions ---")
    mass_tests = [
        ("Gram", 200.0, 260.0),               # 200g / 100g = 2.0 -> 260 kcal
        ("Kilogram", 0.5, 650.0),             # 0.5kg = 500g / 100g = 5.0 -> 650 kcal
        ("Milliliters", 250.0, 325.0),        # 250ml = 250g / 100g = 2.5 -> 325 kcal
        ("Liters", 1.0, 1300.0),              # 1L = 1000g / 100g = 10.0 -> 1300 kcal
    ]
    for unit_name, qty, expected_kcal in mass_tests:
        m = UserMeal(user=user, food_item=rice, food_name="Rice", quantity=qty, unit=unit_name)
        m.save()
        assert m.calories == expected_kcal, f"{unit_name}: Expected {expected_kcal} kcal, got {m.calories}"
        print(f"  [PASS] {qty} {unit_name} -> {m.calories} kcal")

    # =============================================================
    # TEST CASE 7: Fractional and Multi-Quantity Scaling
    # =============================================================
    print("\n--- TEST CASE 7: Fractional & Multi-Quantity Scaling ---")
    # 0.5 Bowl = 75g -> factor 0.75 -> 130 * 0.75 = 97.5 kcal
    m_half = UserMeal(user=user, food_item=rice, food_name="Rice", quantity=0.5, unit="Bowl")
    m_half.save()
    assert m_half.calories == 97.5, f"Expected 97.5 kcal, got {m_half.calories}"
    print(f"  [PASS] 0.5 Bowl Rice = {m_half.calories} kcal (75g).")

    # 2.5 Bowls = 375g -> factor 3.75 -> 130 * 3.75 = 487.5 kcal
    m_multi = UserMeal(user=user, food_item=rice, food_name="Rice", quantity=2.5, unit="Bowl")
    m_multi.save()
    assert m_multi.calories == 487.5, f"Expected 487.5 kcal, got {m_multi.calories}"
    print(f"  [PASS] 2.5 Bowls Rice = {m_multi.calories} kcal (375g).")

    # =============================================================
    # TEST CASE 8: Paneer Masala Scaling (Base is 200g serving)
    # =============================================================
    print("\n--- TEST CASE 8: Paneer Masala (Base gram_equivalent = 200g) ---")
    # 1 Bowl = 150g. Base = 200g. Factor = 150/200 = 0.75. Calories = 320 * 0.75 = 240 kcal
    m_pm = UserMeal(user=user, food_item=paneer_masala, food_name="Paneer Masala", quantity=1.0, unit="Bowl")
    m_pm.save()
    assert m_pm.calories == 240.0, f"Expected 240.0 kcal, got {m_pm.calories}"
    assert m_pm.protein == 9.0, f"Expected 9.0g protein, got {m_pm.protein}"
    print(f"  [PASS] 1 Bowl Paneer Masala = {m_pm.calories} kcal, {m_pm.protein}g protein.")

    # 1 Plate = 350g. Base = 200g. Factor = 350/200 = 1.75. Calories = 320 * 1.75 = 560 kcal
    m_pm_plate = UserMeal(user=user, food_item=paneer_masala, food_name="Paneer Masala", quantity=1.0, unit="Plate")
    m_pm_plate.save()
    assert m_pm_plate.calories == 560.0, f"Expected 560.0 kcal, got {m_pm_plate.calories}"
    print(f"  [PASS] 1 Plate Paneer Masala = {m_pm_plate.calories} kcal (350g: factor 1.75).")

    # =============================================================
    # TEST CASE 9: Immutability of FoodItem Table
    # =============================================================
    print("\n--- TEST CASE 9: FoodItem Table Immutability Check ---")
    # Re-fetch rice and paneer from database
    rice_fresh = FoodItem.objects.get(id=rice.id)
    paneer_fresh = FoodItem.objects.get(id=paneer.id)
    paneer_masala_fresh = FoodItem.objects.get(id=paneer_masala.id)

    assert rice_fresh.calories == 130.0, "FoodItem Rice calories changed!"
    assert rice_fresh.gram_equivalent == 100.0, "FoodItem Rice gram_equivalent changed!"
    assert paneer_fresh.calories == 265.0, "FoodItem Paneer calories changed!"
    assert paneer_masala_fresh.calories == 320.0, "FoodItem Paneer Masala calories changed!"
    print("  [PASS] FoodItem table is 100% UNMODIFIED after multiple user meal logs.")

    print("\n" + "=" * 60)
    print("ALL 9 TEST CASES PASSED WITH 100% ACCURACY!")
    print("=" * 60)

if __name__ == '__main__':
    run_tests()
