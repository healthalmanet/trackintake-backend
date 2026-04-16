from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.views import TokenBlacklistView
from django.conf import settings
from django.http import HttpResponse
def health_check(request):
    return HttpResponse("System is Up!", status=200)



urlpatterns = [
    path('admin/', admin.site.urls),
    path('', health_check),


    path('api/', include('user.urls')),
    path('api/', include('userProfile.urls')),
    path('api/', include('userFood.urls')),
    path('api/', include('owner.urls')),
    path('api/', include('nutritionist.urls')),
    path('api/', include('features.urls')),
    path('api/', include('diet.urls')),


    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/logout/', TokenBlacklistView.as_view(), name='logout'),
    path('api/appointments/', include('appointments.urls')),
    path("api/subscriptions/", include("subscriptions.urls")),
    path('api/', include('chatbot.urls')), 

]