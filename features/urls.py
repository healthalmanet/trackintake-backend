
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from features.consumers import MessageConsumer, ReminderConsumer
from .views import (
    BlogDetailView,
    BlogListCreateView,
    FoodItemListView,
    MarkMessagesReadView,
    MessageListView,
    SendMessageView,
    WeightLogViewSet,
    WaterIntakeLogViewSet,
    CustomReminderViewSet,
    trigger_reminder_check_securely,
)

router = DefaultRouter()

router.register(r'weight', WeightLogViewSet, basename='weight-log')
router.register(r'water', WaterIntakeLogViewSet, basename='water-log')
router.register(r'reminders', CustomReminderViewSet, basename='reminder')

urlpatterns = [
    
    #Messaging 
    path('messages/', MessageListView.as_view(), name='message-list'),
    path('messages/send/', SendMessageView.as_view(), name='send-message'),
    path('messages/mark-read/', MarkMessagesReadView.as_view(), name='mark-messages-read'),

      #Blog APIs
    path('blogs/', BlogListCreateView.as_view(), name='blog-list-create'),
    path('blogs/<int:pk>/', BlogDetailView.as_view(), name='blog-detail'),

    path('foods/', FoodItemListView.as_view(), name='food-list'),

    path('trigger-reminders/', trigger_reminder_check_securely, name='trigger-reminders'),

    path('', include(router.urls)), 

]

websocket_urlpatterns = [
    path('ws/reminders/', ReminderConsumer.as_asgi()),
    path("ws/messages/", MessageConsumer.as_asgi()),
]
