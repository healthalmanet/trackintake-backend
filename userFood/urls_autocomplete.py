from django.urls import path

from .views_autocomplete import FoodSearchView

urlpatterns = [
    path('foods/search/', FoodSearchView.as_view(), name='food-search'),
]

