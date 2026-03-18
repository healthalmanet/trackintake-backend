from django.urls import path
from .webhooks import RazorpayWebhook
from .views import (
    CreateOrderView,
    PlanListView,
    MySubscriptionView,
    NutritionistRegistrationOrderView,
    UserRegistrationOrderView,PayConsultationFeeView
)
from .views import VerifyPaymentView



urlpatterns = [
    path("plans/", PlanListView.as_view()),
    path("my/", MySubscriptionView.as_view()),
    path("create-order/", CreateOrderView.as_view()),
    path("razorpay/webhook/", RazorpayWebhook.as_view()),
    path("nutritionist-registration-order/", NutritionistRegistrationOrderView.as_view()),
    path("user-registration-order/", UserRegistrationOrderView.as_view()),
    path("verify-payment/", VerifyPaymentView.as_view()),
    path("pay-consultation/", PayConsultationFeeView.as_view()),
]