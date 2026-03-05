from django.urls import path
from .views import DietPlanView, PreviousDietPlansView


urlpatterns = [
    
  # User Profile API  
  path('diet/', DietPlanView.as_view(), name='generate-diet-plan'),
  path('diet-plan/history/', PreviousDietPlansView.as_view(), name='diet-plan-history'),

]
