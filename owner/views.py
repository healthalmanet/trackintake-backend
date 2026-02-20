from datetime import timedelta
from django.utils.timezone import now
from django.db.models import Count
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework import permissions

from userFood.models import UserMeal
from userProfile.models import UserProfile
from user.models import Feedback
from user.serializers import FeedbackSerializer
from utils.utils import role_required
from user.models import User

class OwnerDashboardView(APIView):
    @role_required(["owner"])
    def get(self, request):
        today = now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        # Core Metrics
        total_users = User.objects.filter(role="user").count()
        new_users_week = User.objects.filter(role="user", date_joined__gte=week_ago).count()
        new_users_month = User.objects.filter(role="user", date_joined__gte=month_ago).count()
        active_patients = UserMeal.objects.filter(date__gte=week_ago).values("user").distinct().count()

        estimated_revenue = active_patients * 49
        meals_logged_week = UserMeal.objects.filter(date__gte=week_ago).count()
        meals_logged_month = UserMeal.objects.filter(date__gte=month_ago).count()

        # Country-wise User Count
        users_by_country = (
            UserProfile.objects.values("country")
            .annotate(user_count=Count("id"))
            .order_by("-user_count")
        )

        # ✅ Feedback Integration with user email
        feedbacks_count = Feedback.objects.count()
        latest_feedbacks = Feedback.objects.select_related('user').order_by('-created_at')[:5]
        feedback_data = FeedbackSerializer(latest_feedbacks, many=True).data

        promotions = [
            {"campaign": "Instagram Ad", "reach": "10k+", "status": "Running"},
            {"campaign": "Referral Program", "reach": "5k+", "status": "Ended"},
        ]

        return Response({
            "date": str(today),
            "user_stats": {
                "total_users": total_users,
                "new_users_week": new_users_week,
                "new_users_month": new_users_month,
                "active_patients_week": active_patients,
            },
            "usage": {
                "meals_logged_week": meals_logged_week,
                "meals_logged_month": meals_logged_month,
            },
            "revenue": f"₹{estimated_revenue}",
            "users_by_country": users_by_country,
            "feedback_summary": {
                "feedback_collected": feedbacks_count,
                "latest_feedbacks": feedback_data
            },
            "promotions": promotions,
            "message": "Owner dashboard data fetched successfully"
        }, status=status.HTTP_200_OK)

##############################################OPERATOR DASHBOARD VIEW#################################################################
class IsOperator(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "operator"
