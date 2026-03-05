from django.urls import path
from .views import OwnerDashboardView


urlpatterns = [
    
  path('owner/', OwnerDashboardView.as_view(), name='owner-dashboard'),

]
