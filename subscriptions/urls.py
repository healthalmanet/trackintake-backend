from .webhooks import RazorpayWebhook
from django.urls import path
from .views import (
    CreateOrderView,
    PlanListView,
    MySubscriptionView,
)

urlpatterns = [
    path("plans/", PlanListView.as_view()),
    path("my/", MySubscriptionView.as_view()),   # ✅ THIS WAS MISSING
    path("create-order/", CreateOrderView.as_view()),
    path("razorpay/webhook/", RazorpayWebhook.as_view()),
]
