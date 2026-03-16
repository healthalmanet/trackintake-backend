
from django.urls import path, include
from userFood.views import DailyUserMealSummaryView, UserMealViewSet, targetNutrients, targetNutrientsUpdate
from rest_framework.routers import DefaultRouter
from .views import FoodSuggestionView
router = DefaultRouter()




router.register(r'logmeals', UserMealViewSet, basename='user-meals')

urlpatterns = [
       # #Calorie recommendation endpoint also fat,protein,carbs
    path('recommend-calories/', targetNutrients, name='recommend_calories'),
    ######calorie tracking ######## also fat,protein,carbs
    path('daily-calorie-summary/', targetNutrientsUpdate.as_view(), name='daily_calorie_summary'),
    
    #7day track
    path('nutrition7day/', DailyUserMealSummaryView.as_view()),


    path('', include(router.urls)), 
    path("suggest-foods/", FoodSuggestionView.as_view(), name="suggest-foods"),

]
