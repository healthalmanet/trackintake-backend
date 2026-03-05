from django.urls import path
from .webhooks import RazorpayWebhook
from .views import (
    CreateOrderView,
    PlanListView,
    MySubscriptionView,
    NutritionistRegistrationOrderView,
)

urlpatterns = [
    path("plans/", PlanListView.as_view()),
    path("my/", MySubscriptionView.as_view()),
    path("create-order/", CreateOrderView.as_view()),
    path("razorpay/webhook/", RazorpayWebhook.as_view()),
    path("nutritionist-registration-order/", NutritionistRegistrationOrderView.as_view()),
]