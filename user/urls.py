from django.urls import path, include
from .views import (
    FeedbackCreateView,
    RegisterView,
    MyTokenObtainPairView,
    ForgotPasswordView,
    ResetPasswordView,
    GoogleLogin,
    FacebookLogin,
    SendOTPView,
    VerifyOTPView,
    get_feedback_for_recommendation,
    submit_diet_feedback,
)
from .integration_views import (
    IntegrationRegisterView,
    IntegrationPlanListView,
    IntegrationCreateOrderView,
    IntegrationVerifyPaymentView,
    IntegrationCheckSubscriptionView,
    IntegrationLabReportViewSet,
    IntegrationUserProfileView,
    IntegrationDietPlanView,
)

urlpatterns = [

    path('send-otp/', SendOTPView.as_view(), name='send-otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),


    path('signup/', RegisterView.as_view(), name='signup'),

    path('login/', MyTokenObtainPairView.as_view(), name='login'),
    

    path('accounts/', include('allauth.socialaccount.urls')),

    path('google/', GoogleLogin.as_view(), name='google_login'),

    path('facebook/', FacebookLogin.as_view(), name='facebook_login'),

    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),

    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),


    # User Integration APIs
    path('integration/register/', IntegrationRegisterView.as_view(), name='integration-register'),
    path('integration/plans/', IntegrationPlanListView.as_view(), name='integration-plans'),
    path('integration/create-order/', IntegrationCreateOrderView.as_view(), name='integration-create-order'),
    path('integration/verify-payment/', IntegrationVerifyPaymentView.as_view(), name='integration-verify-payment'),
    path('integration/check-subscription/', IntegrationCheckSubscriptionView.as_view(), name='integration-check-subscription'),
    path('integration/profile/', IntegrationUserProfileView.as_view(), name='integration-profile'),
    path('integration/lab-reports/', IntegrationLabReportViewSet.as_view({'get': 'list', 'post': 'create'}), name='integration-lab-reports-list'),
    path('integration/lab-reports/<int:pk>/', IntegrationLabReportViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='integration-lab-reports-detail'),
    path('integration/diet/', IntegrationDietPlanView.as_view(), name='integration-diet'),


    #User Diet Feedback APIs
    path('diet/feedback/', submit_diet_feedback, name='submit_diet_feedback'),
    
    path('diet/feedback/<int:recommendation_id>/', get_feedback_for_recommendation, name='get_feedback_for_recommendation'),

    #User Application Feedback APIs
    # # # ⭐ User Feedback on Application (POST)
    path('feedback/create/', FeedbackCreateView.as_view(), name='feedback-create'),
]