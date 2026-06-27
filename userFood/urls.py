
from django.urls import path, include
from userFood.views import DailyUserMealSummaryView, UserMealViewSet, targetNutrients, targetNutrientsUpdate
from userFood.views_attributes import (
    FoodAttributesDetailView,
    AttributeOptionsView,
    MealAttributesView,
    FoodWithAttributesView,
    FoodWithAttributesByNameView,
    MealWithAttributesViewSet
)

from rest_framework.routers import DefaultRouter
from .views import FoodSuggestionView
from .urls_autocomplete import urlpatterns as autocomplete_urlpatterns

# Autocomplete/search endpoints (DB-first; no Gemini during typing)
router = DefaultRouter()
router.register(r'logmeals', UserMealViewSet, basename='user-meals')
router.register(r'logmeals_with_attributes',
                MealWithAttributesViewSet, basename='user-meals-with-attributes')

urlpatterns = [
    # Calorie recommendation endpoint
    path('recommend-calories/', targetNutrients, name='recommend_calories'),

    # Calorie tracking
    path('daily-calorie-summary/', targetNutrientsUpdate.as_view(),
         name='daily_calorie_summary'),

    # 7-day track
    path('nutrition7day/', DailyUserMealSummaryView.as_view()),

    # Food Attributes APIs
    path('foods/<int:food_id>/attributes/',
         FoodAttributesDetailView.as_view(), name='food-attributes'),
    path('foods/by-name/<str:name>/',
         FoodWithAttributesByNameView.as_view(), name='food-with-attributes-by-name'),
    path('foods/<int:pk>/', FoodWithAttributesView.as_view(),
         name='food-with-attributes'),
    path('attributes/<int:attribute_id>/options/',
         AttributeOptionsView.as_view(), name='attribute-options'),

    path('meals/<int:meal_id>/attributes/',
         MealAttributesView.as_view(), name='meal-attributes'),

    # Router URLs
    path('', include(router.urls)),

    # Food suggestions
    path("suggest-foods/", FoodSuggestionView.as_view(), name="suggest-foods"),
]
urlpatterns += autocomplete_urlpatterns