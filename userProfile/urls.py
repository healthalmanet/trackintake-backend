from django.urls import include, path
from .views import LabReportViewSet, UserProfileView
from rest_framework.routers import DefaultRouter

router = DefaultRouter()




router.register(r'lab-reports', LabReportViewSet, basename='labreport')

urlpatterns = [
    path('profile/', UserProfileView.as_view(), name='user-profile'),

    path('', include(router.urls)), 

]
