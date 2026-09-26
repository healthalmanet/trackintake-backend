import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from userFood.models import FoodItem, UserMeal

User = get_user_model()

def test_api_endpoints():
    print("=" * 60)
    print("TESTING API ENDPOINTS")
    print("=" * 60)

    user = User.objects.first()
    client = APIClient()
    client.force_authenticate(user=user)

    # 1. Test Autocomplete Search
    print("\n--- 1. Testing /api/foods/search/ for 'paneer' ---")
    res = client.get('/api/foods/search/?q=paneer')
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    results = res.data.get("results", [])
    assert len(results) >= 2, f"Expected at least 2 results (Paneer, Paneer Masala), got {len(results)}"
    
    names = [r["name"] for r in results]
    assert "Paneer" in names, "Paneer missing from search results"
    assert "Paneer Masala" in names, "Paneer Masala missing from search results"
    # Verify first result is exact match "Paneer"
    assert results[0]["name"] == "Paneer", f"Expected Paneer as rank 0, got {results[0]['name']}"
    assert results[0]["gram_equivalent"] == 100.0
    assert results[0]["calories_per_serving"] == 265.0
    print(f"  [PASS] Autocomplete returned {len(results)} items. Top item: {results[0]['name']} with {results[0]['serving_hint']}")

    # 2. Test Recent Meals
    print("\n--- 2. Testing /api/logmeals/recent/ ---")
    res_recent = client.get('/api/logmeals/recent/')
    assert res_recent.status_code == 200, f"Expected 200, got {res_recent.status_code}"
    recent_meals = res_recent.data.get("recent", res_recent.data)
    assert len(recent_meals) > 0, "Expected at least 1 recent meal"
    recent_names = [m["food_name"] for m in recent_meals]
    print(f"  [PASS] Recent meals returned {len(recent_meals)} distinct items: {recent_names[:4]}")

    print("\n" + "=" * 60)
    print("ALL API ENDPOINT TESTS PASSED WITH 100% ACCURACY!")
    print("=" * 60)

if __name__ == '__main__':
    test_api_endpoints()
