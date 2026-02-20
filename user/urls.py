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





    #User Diet Feedback APIs
    path('diet/feedback/', submit_diet_feedback, name='submit_diet_feedback'),
    
    path('diet/feedback/<int:recommendation_id>/', get_feedback_for_recommendation, name='get_feedback_for_recommendation'),

    #User Application Feedback APIs
    # # # ⭐ User Feedback on Application (POST)
    path('feedback/create/', FeedbackCreateView.as_view(), name='feedback-create'),
]