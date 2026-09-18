from datetime import date, datetime, time
from concurrent.futures import ThreadPoolExecutor
import copy
import traceback

from django.contrib.auth import get_user_model
from django.contrib.postgres.search import TrigramSimilarity
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.timezone import now

from django.http import HttpResponse
from rest_framework import filters, generics, permissions, serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django_filters.rest_framework import DjangoFilterBackend

from subscriptions.models import Plan, UserSubscription
from subscriptions.services import activate_plan_for_user, check_patient_ai_diet_access

from nutritionist.models import PatientAssignment, NutritionistProfile
from nutritionist.permissions import IsVerifiedNutritionist

from diet.models import DietRecommendation
from diet.serializers import DietRecommendationSerializer
from diet.tasks import generate_ai_diet_task

from userProfile.models import LabReport, UserProfile
from userProfile.serializers import LabReportSerializer, UserProfileSerializer

from userFood.models import FoodItem, UserMeal

from user.models import User

from utils.gemini import fetch_nutrition_from_gemini, food_search_gemini
from utils.generative import (
    generate_ai_plan_for_patient,
    _serialize_user_profile,
    _serialize_lab_report,
    _calculate_target_nutrients,
)
from utils.pagination import StandardResultsSetPagination

# from ml_model.src.generator import generate_diet_plan

from .models import PatientAssignment
from .serializers import (
    CreatePatientSerializer,
    DietRecommendationDetailSerializer,
    UserSerializer1,
    PatientProfileSerializer1,
    UserMealSerializer1,
    DietRecommendationWithPatientSerializer1,
)
from .bulk_upload import generate_patient_template_excel, process_patient_bulk_upload

User = get_user_model()
executor = ThreadPoolExecutor(max_workers=2)
FUZZY_MATCH_THRESHOLD = 0.9


# ==============================================================================
# Permission Classes
# ==============================================================================

class IsNutritionist(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'nutritionist'


class IsPatient(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'user'


# ==============================================================================
# Nutritionist — User & Patient Management
# ==============================================================================

class UserListForNutritionistView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]
    serializer_class = UserSerializer1
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['email', 'full_name']
    ordering_fields = ['date_joined', 'full_name']

    def get_queryset(self):
        return User.objects.filter(role='user').select_related('userprofile').order_by('-date_joined')


class AssignPatientAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]

    def post(self, request, *args, **kwargs):
        patient_id = request.data.get('patient_id')
        if not patient_id:
            return Response({'error': 'patient_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check practitioner active capacity limit
        from subscriptions.permissions import check_nutritionist_patient_capacity
        can_add, current_count, max_limit, err_msg = check_nutritionist_patient_capacity(request.user)
        if not can_add:
            return Response({
                'error': err_msg,
                'detail': err_msg,
                'upgrade_required': True,
                'current_count': current_count,
                'max_limit': max_limit
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            patient = User.objects.get(id=patient_id, role='user')
            assignment, created = PatientAssignment.objects.get_or_create(
                nutritionist=request.user,
                patient=patient
            )
            message = 'Patient assigned successfully.' if created else 'Patient was already assigned.'
            return Response({'message': message}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'error': 'Patient with the given ID not found.'}, status=status.HTTP_404_NOT_FOUND)


class AssignedPatientsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]
    serializer_class = UserSerializer1
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['email']
    search_fields = ['full_name']

    def get_queryset(self):
        assigned_patient_ids = PatientAssignment.objects.filter(
            nutritionist=self.request.user
        ).values_list('patient_id', flat=True)
        return User.objects.filter(id__in=assigned_patient_ids).select_related('userprofile')


class NutritionistCreatePatientView(generics.GenericAPIView):
    serializer_class = CreatePatientSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if request.user.role != "nutritionist":
            return Response({"detail": "Only nutritionists can create patients."}, status=403)

        # Check practitioner active capacity limit
        from subscriptions.permissions import check_nutritionist_patient_capacity
        can_add, current_count, max_limit, err_msg = check_nutritionist_patient_capacity(request.user)
        if not can_add:
            return Response({
                'error': err_msg,
                'detail': err_msg,
                'upgrade_required': True,
                'current_count': current_count,
                'max_limit': max_limit
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                user = serializer.save()
                PatientAssignment.objects.update_or_create(
                    patient=user,
                    defaults={'nutritionist': request.user}
                )
                # ❌ Free plan assign nahi karo
                # Patient login karke khud plan kharide

                return Response(
                    {"detail": "Patient created and assigned successfully."},
                    status=201
                )
        except Exception as e:
            return Response({"detail": str(e)}, status=400)


class DownloadPatientTemplateView(APIView):
    """
    Downloads the pre-filled Excel template (.xlsx) with column headers,
    required field markers, and 10 realistic example patient records.
    """
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]

    def get(self, request, *args, **kwargs):
        from subscriptions.permissions import check_nutritionist_feature
        allowed, err_msg, plan_name = check_nutritionist_feature(request.user, "nutri_bulk_upload_allowed")
        if not allowed:
            return Response({"detail": err_msg, "error": err_msg, "upgrade_required": True, "feature": "nutri_bulk_upload_allowed", "current_plan": plan_name}, status=status.HTTP_403_FORBIDDEN)

        try:
            excel_content = generate_patient_template_excel()
            response = HttpResponse(
                excel_content,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="trackintake_patient_import_template.xlsx"'
            response['Access-Control-Expose-Headers'] = 'Content-Disposition'
            return response
        except Exception as e:
            return Response({"detail": f"Failed to generate template: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BulkUploadPatientsView(APIView):
    """
    Accepts an Excel (.xlsx/.xls) file and bulk creates up to 1000s of patients,
    attaches profiles & lab reports, and links them to the requesting nutritionist.
    """
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]

    def post(self, request, *args, **kwargs):
        from subscriptions.permissions import check_nutritionist_feature
        allowed, err_msg, plan_name = check_nutritionist_feature(request.user, "nutri_bulk_upload_allowed")
        if not allowed:
            return Response({"detail": err_msg, "error": err_msg, "upgrade_required": True, "feature": "nutri_bulk_upload_allowed", "current_plan": plan_name}, status=status.HTTP_403_FORBIDDEN)

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response(
                {"detail": "No file uploaded. Please upload a valid .xlsx Excel file."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not uploaded_file.name.lower().endswith(('.xlsx', '.xls')):
            return Response(
                {"detail": "Invalid file format. Only .xlsx or .xls files are supported."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            result = process_patient_bulk_upload(uploaded_file, request.user)
            if not result.get("success", True):
                return Response(result, status=status.HTTP_400_BAD_REQUEST)

            status_code = status.HTTP_201_CREATED if result["created_count"] > 0 else status.HTTP_200_OK
            return Response(result, status=status_code)
        except Exception as e:
            return Response(
                {"detail": f"An error occurred while processing bulk upload: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ==============================================================================
# Nutritionist — Patient Profile & Lab Reports
# ==============================================================================

class PatientProfileDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]

    class PatientProfileSerializer1(serializers.ModelSerializer):
        email = serializers.EmailField(source='user.email', read_only=True)
        full_name = serializers.CharField(source='user.full_name', read_only=True)
        bmi = serializers.FloatField(read_only=True)

        class Meta:
            model = UserProfile
            fields = [
                'email', 'full_name', 'date_of_birth', 'gender', 'occupation',
                'height_cm', 'weight_kg', 'bmi', 'activity_level', 'goal',
                'diet_type', 'allergies', 'is_diabetic', 'is_hypertensive',
                'has_heart_condition', 'has_thyroid_disorder', 'has_arthritis',
                'has_gastric_issues', 'other_chronic_condition', 'family_history'
            ]
            read_only_fields = ['email', 'full_name', 'bmi']

    def get(self, request, patient_id):
        if not PatientAssignment.objects.filter(nutritionist=request.user, patient_id=patient_id).exists():
            return Response({'error': 'You are not assigned to this patient.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            user_profile = UserProfile.objects.select_related('user').get(user_id=patient_id)
            profile_serializer = self.PatientProfileSerializer1(user_profile)

            lab_report_data = None
            latest_lab_report = LabReport.objects.filter(user_id=patient_id).order_by('-report_date').first()
            if latest_lab_report:
                lab_report_data = LabReportSerializer(latest_lab_report).data

            return Response({
                'profile': profile_serializer.data,
                'latest_lab_report': lab_report_data
            }, status=status.HTTP_200_OK)

        except UserProfile.DoesNotExist:
            return Response({'error': 'Patient profile not found.'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, patient_id):
        if not PatientAssignment.objects.filter(nutritionist=request.user, patient_id=patient_id).exists():
            return Response({'error': 'You are not assigned to this patient.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            user_profile = UserProfile.objects.get(user_id=patient_id)
        except UserProfile.DoesNotExist:
            return Response({'error': 'Patient profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.PatientProfileSerializer1(instance=user_profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PatientLabReportsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]
    serializer_class = LabReportSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['report_date']
    ordering_fields = ['report_date']

    def get_queryset(self):
        patient_id = self.kwargs['patient_id']
        if not PatientAssignment.objects.filter(nutritionist=self.request.user, patient_id=patient_id).exists():
            raise PermissionDenied("You are not assigned to this patient.")
        return LabReport.objects.filter(user_id=patient_id).order_by('-report_date')


class PatientLabReportListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]
    serializer_class = LabReportSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['report_date']
    ordering_fields = ['report_date']

    def get_queryset(self):
        patient_id = self.kwargs['patient_id']
        if not PatientAssignment.objects.filter(nutritionist=self.request.user, patient_id=patient_id).exists():
            raise PermissionDenied("You are not assigned to this patient.")
        return LabReport.objects.filter(user_id=patient_id)

    def create(self, request, *args, **kwargs):
        from subscriptions.permissions import check_nutritionist_feature
        allowed, err_msg, plan_name = check_nutritionist_feature(request.user, "nutri_lab_reports_allowed")
        if not allowed:
            return Response({
                "error": err_msg,
                "detail": err_msg,
                "upgrade_required": True,
                "feature": "nutri_lab_reports_allowed",
                "current_plan": plan_name
            }, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        patient_id = self.kwargs['patient_id']
        if not PatientAssignment.objects.filter(nutritionist=self.request.user, patient_id=patient_id).exists():
            raise PermissionDenied("You are not assigned to this patient.")
        try:
            patient_user = User.objects.get(pk=patient_id)
        except User.DoesNotExist:
            raise NotFound("Patient not found.")
        serializer.save(user=patient_user)


class PatientLabReportDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]
    serializer_class = LabReportSerializer
    lookup_field = 'pk'

    def get_queryset(self):
        patient_id = self.kwargs['patient_id']
        if not PatientAssignment.objects.filter(nutritionist=self.request.user, patient_id=patient_id).exists():
            raise PermissionDenied("You are not assigned to this patient.")
        return LabReport.objects.filter(user_id=patient_id)


# ==============================================================================
# Nutritionist — Meal Logs & Nutrition Summary
# ==============================================================================

class PatientMealLogView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]
    serializer_class = UserMealSerializer1
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['consumed_at', 'date']
    ordering_fields = ['consumed_at']
    ordering = ['-consumed_at']

    def get_queryset(self):
        patient_id = self.kwargs['patient_id']
        if not PatientAssignment.objects.filter(nutritionist=self.request.user, patient_id=patient_id).exists():
            raise PermissionDenied("You are not assigned to this patient.")
        return UserMeal.objects.filter(user_id=patient_id).select_related('food_item').order_by('-consumed_at')


class PatientDailySummaryView(APIView):
    permission_classes = [IsAuthenticated, IsNutritionist]

    def get(self, request, patient_id):
        if not PatientAssignment.objects.filter(nutritionist=request.user, patient_id=patient_id).exists():
            return Response({'error': 'Not assigned to this patient.'}, status=403)

        date_str = request.query_params.get('date')
        if not date_str:
            return Response({"error": "A 'date' query parameter is required."}, status=400)

        target_date = parse_date(date_str)
        if not target_date:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=400)

        start_of_day = datetime.combine(target_date, time.min)
        end_of_day = datetime.combine(target_date, time.max)

        meals = UserMeal.objects.filter(user_id=patient_id, consumed_at__range=(start_of_day, end_of_day))
        totals = meals.aggregate(
            total_calories=Sum("calories", default=0),
            total_protein=Sum("protein", default=0),
            total_carbs=Sum("carbs", default=0),
            total_fats=Sum("fats", default=0),
            total_sugar=Sum("sugar", default=0),
            total_fiber=Sum("fiber", default=0),
        )

        return Response({
            "patient_id": patient_id,
            "date": target_date,
            **{k.replace("total_", ""): v for k, v in totals.items()}
        })


class TargetNutrientsForPatientView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]

    def get(self, request, patient_id):
        if not PatientAssignment.objects.filter(nutritionist=request.user, patient_id=patient_id).exists():
            return Response({'error': 'You are not assigned to this patient.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            current_date_str = request.query_params.get('current_date')
            today = parse_date(current_date_str) if current_date_str else date.today()

            profile = UserProfile.objects.get(user_id=patient_id)
            dob = profile.date_of_birth
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

            weight = profile.weight_kg
            height = profile.height_cm
            gender = profile.gender
            activity_level = profile.activity_level
            goal = profile.goal

            bmr = 10 * weight + 6.25 * height - 5 * age + (5 if gender == "male" else -161)

            activity_multipliers = {
                "sedentary": 1.2, "light": 1.3, "lightly_active": 1.3,
                "moderate": 1.45, "active": 1.6, "very_active": 1.75
            }
            maintenance_calories = bmr * activity_multipliers.get(activity_level.lower(), 1.2)

            if goal == "Gain Weight":
                recommended_calories = maintenance_calories * 1.15
                target_weight = weight + 5
            elif goal == "Lose Weight":
                recommended_calories = maintenance_calories * 0.8
                target_weight = weight - 5
            else:
                recommended_calories = maintenance_calories
                target_weight = weight

            recommended_calories = round(recommended_calories)
            protein_g = round(weight * 1.8)
            fats_g = round(weight * 0.8)
            carbs_calories = recommended_calories - (protein_g * 4 + fats_g * 9)
            carbs_g = round(carbs_calories / 4) if carbs_calories > 0 else 0
            sugar_g = round((recommended_calories * 0.1) / 4)
            fiber_g = round((recommended_calories / 1000) * 14)

            base_water_ml = weight * 35
            activity_water_bonus = {
                "sedentary": 0, "light": 250, "lightly_active": 250,
                "moderate": 500, "active": 750, "very_active": 1000
            }
            recommended_water_ml = base_water_ml + activity_water_bonus.get(activity_level.lower(), 0)

            return Response({
                "bmr": round(bmr),
                "maintenance_calories": round(maintenance_calories),
                "recommended_calories": recommended_calories,
                "macronutrients": {
                    "protein_g": protein_g, "carbs_g": carbs_g,
                    "fats_g": fats_g, "sugar_g": sugar_g, "fiber_g": fiber_g
                },
                "water": {"recommended_ml": round(recommended_water_ml)},
                "weight_target": {
                    "current_weight_kg": round(weight, 1),
                    "target_weight_kg": round(target_weight, 1),
                    "goal": goal
                },
                "activity_level": activity_level
            })

        except UserProfile.DoesNotExist:
            return Response({'error': 'Patient profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==============================================================================
# Nutritionist — Diet Plan Management
# ==============================================================================

class NutritionistPatientDietRecommendationsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]
    serializer_class = DietRecommendationWithPatientSerializer1

    def get_queryset(self):
        patient_id = self.kwargs['patient_id']
        if not PatientAssignment.objects.filter(nutritionist=self.request.user, patient_id=patient_id).exists():
            raise PermissionDenied("You are not assigned to this patient.")
        return DietRecommendation.objects.filter(user_id=patient_id).select_related('user', 'reviewed_by').order_by('-created_at')


class AllAssignedDietPlansListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]
    serializer_class = DietRecommendationWithPatientSerializer1
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status']
    search_fields = ['user__full_name', 'user__email']
    ordering_fields = ['created_at', 'for_week_starting']
    ordering = ['-created_at']

    def get_queryset(self):
        assigned_patient_ids = PatientAssignment.objects.filter(
            nutritionist=self.request.user
        ).values_list('patient_id', flat=True)
        return DietRecommendation.objects.filter(user_id__in=assigned_patient_ids).select_related('user', 'reviewed_by')


class ApproveOrRejectDietView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]

    def post(self, request, pk=None, *args, **kwargs):
        action = request.data.get("action")
        comment = request.data.get("comment", "")

        if action not in ["approved", "rejected"]:
            return Response({'error': 'Invalid action. Use "approved" or "rejected".'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            recommendation = DietRecommendation.objects.get(id=pk)
            if not PatientAssignment.objects.filter(nutritionist=request.user, patient=recommendation.user).exists():
                return Response({'error': 'You are not assigned to this patient.'}, status=status.HTTP_403_FORBIDDEN)

            recommendation.status = action
            recommendation.reviewed_by = request.user
            recommendation.nutritionist_comment = comment
            recommendation.save()
            return Response({'message': f'Diet plan has been {action}.'}, status=status.HTTP_200_OK)
        except DietRecommendation.DoesNotExist:
            return Response({'error': 'Recommendation not found'}, status=status.HTTP_404_NOT_FOUND)


class UpdateRetrainingFlagsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]

    def post(self, request, pk=None, recommendation_id=None, *args, **kwargs):
        plan_id = pk or recommendation_id
        notes = request.data.get("notes") or request.data.get("feedback") or request.data.get("comment", "")
        approved_raw = request.data.get("approved_for_retraining")
        if approved_raw is None:
            approved_raw = request.data.get("approved", True)

        if isinstance(approved_raw, str):
            approved_for_retraining = approved_raw.strip().lower() in ["true", "1", "yes"]
        else:
            approved_for_retraining = bool(approved_raw)

        try:
            recommendation = DietRecommendation.objects.get(id=plan_id)
            if not PatientAssignment.objects.filter(nutritionist=request.user, patient=recommendation.user).exists() and recommendation.reviewed_by != request.user:
                return Response({'error': 'You are not assigned to this patient.'}, status=status.HTTP_403_FORBIDDEN)

            recommendation.nutritionist_retraining_notes = notes
            recommendation.approved_for_retraining = approved_for_retraining
            recommendation.save(update_fields=['nutritionist_retraining_notes', 'approved_for_retraining', 'updated_at'])
            return Response({'message': 'Retraining feedback submitted successfully.'}, status=status.HTTP_200_OK)
        except DietRecommendation.DoesNotExist:
            return Response({'error': 'Recommendation not found.'}, status=status.HTTP_404_NOT_FOUND)


class EditDietPlanView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]
    serializer_class = DietRecommendationDetailSerializer
    queryset = DietRecommendation.objects.select_related('user', 'reviewed_by').all()

    def _get_or_create_food_item(self, food_name: str):
        original_food_name = food_name.strip()
        if not original_food_name:
            return None

        food = FoodItem.objects.filter(name__iexact=original_food_name).first()
        if food:
            return food

        if len(original_food_name.split()) > 1:
            food = FoodItem.objects.annotate(
                similarity=TrigramSimilarity('name', original_food_name)
            ).filter(similarity__gt=FUZZY_MATCH_THRESHOLD).order_by('-similarity').first()
            if food:
                return food

        try:
            gemini_food_item = food_search_gemini(original_food_name)
            if not gemini_food_item:
                return None

            if gemini_food_item.name.lower() != original_food_name.lower():
                existing_food = FoodItem.objects.filter(name__iexact=original_food_name).first()
                if existing_food:
                    gemini_food_item.delete()
                    return existing_food
                else:
                    gemini_food_item.name = original_food_name
                    gemini_food_item.save()

            return gemini_food_item
        except Exception as e:
            print(f"❌ Error processing '{original_food_name}': {e}")
            return None

    def _format_food_for_plan(self, food: FoodItem) -> dict:
        return {
            "food_name": food.name,
            "Gram_Equivalent": food.gram_equivalent,
            "Calories": food.calories,
            "Protein": food.protein,
            "Carbs": food.carbs,
            "Fats": food.fats,
            "Fiber": food.fiber,
            "Sugar": food.sugar,
        }

    @transaction.atomic
    def patch(self, request, pk=None, recommendation_id=None, *args, **kwargs):
        from subscriptions.permissions import check_nutritionist_feature
        allowed, err_msg, plan_name = check_nutritionist_feature(request.user, "nutri_manual_diet_allowed")
        if not allowed:
            return Response({
                "error": err_msg,
                "detail": err_msg,
                "upgrade_required": True,
                "feature": "nutri_manual_diet_allowed",
                "current_plan": plan_name
            }, status=status.HTTP_403_FORBIDDEN)

        plan_id = pk or recommendation_id
        try:
            recommendation = DietRecommendation.objects.select_for_update().get(pk=plan_id)
        except DietRecommendation.DoesNotExist:
            return Response({'error': 'Recommendation not found.'}, status=status.HTTP_404_NOT_FOUND)

        new_meals_data = request.data.get('meals')
        if new_meals_data and isinstance(new_meals_data, dict):
            db_meals = copy.deepcopy(recommendation.meals or {})
            for day_key, meals_for_day in new_meals_data.items():
                if not isinstance(meals_for_day, dict):
                    continue
                normalized_day_key = day_key.strip().title()
                existing_key = next((k for k in db_meals if k.strip().title() == normalized_day_key), normalized_day_key)
                db_meals.setdefault(existing_key, {})

                for meal_slot, meal_info in meals_for_day.items():
                    food_name = meal_info.get("item") if isinstance(meal_info, dict) else None
                    if not food_name:
                        continue
                    food_item_obj = self._get_or_create_food_item(food_name)
                    if food_item_obj:
                        db_meals[existing_key][meal_slot] = self._format_food_for_plan(food_item_obj)
                    else:
                        db_meals[existing_key].pop(meal_slot, None)

            recommendation.meals = db_meals

        update_fields = ['meals', 'updated_at']

        if 'nutritionist_comment' in request.data:
            recommendation.nutritionist_comment = request.data['nutritionist_comment']
            update_fields.append('nutritionist_comment')

        if 'status' in request.data:
            recommendation.status = request.data['status']
            update_fields.append('status')
        elif new_meals_data:
            recommendation.status = 'pending'
            update_fields.append('status')

        if 'approved_for_retraining' in request.data:
            recommendation.approved_for_retraining = request.data['approved_for_retraining']
            update_fields.append('approved_for_retraining')

        if 'nutritionist_retraining_notes' in request.data:
            recommendation.nutritionist_retraining_notes = request.data['nutritionist_retraining_notes']
            update_fields.append('nutritionist_retraining_notes')

        recommendation.reviewed_by = request.user
        update_fields.append('reviewed_by')

        recommendation.save(update_fields=update_fields)

        serializer = self.get_serializer(recommendation)
        return Response({
            'message': 'Diet plan updated successfully.',
            'data': serializer.data
        }, status=status.HTTP_200_OK)


class ArchiveDietPlanView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]

    def patch(self, request, pk=None, *args, **kwargs):
        return self._archive(request, pk)

    def post(self, request, pk=None, *args, **kwargs):
        return self._archive(request, pk)

    def _archive(self, request, pk):
        try:
            plan = DietRecommendation.objects.get(id=pk)
            if not PatientAssignment.objects.filter(nutritionist=request.user, patient=plan.user).exists() and plan.reviewed_by != request.user:
                return Response({'error': 'You are not assigned to this patient.'}, status=status.HTTP_403_FORBIDDEN)
            plan.is_deleted = True
            plan.save(update_fields=['is_deleted', 'updated_at'])
            return Response({"message": "The diet plan has been successfully archived."}, status=status.HTTP_200_OK)
        except DietRecommendation.DoesNotExist:
            return Response({'error': 'Diet plan not found.'}, status=status.HTTP_404_NOT_FOUND)


class RestoreDietPlanView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]

    def patch(self, request, pk=None, *args, **kwargs):
        return self._restore(request, pk)

    def post(self, request, pk=None, *args, **kwargs):
        return self._restore(request, pk)

    def _restore(self, request, pk):
        try:
            plan = DietRecommendation.objects.get(id=pk)
            if not PatientAssignment.objects.filter(nutritionist=request.user, patient=plan.user).exists() and plan.reviewed_by != request.user:
                return Response({'error': 'You are not assigned to this patient.'}, status=status.HTTP_403_FORBIDDEN)
            plan.is_deleted = False
            plan.save(update_fields=['is_deleted', 'updated_at'])
            return Response({"message": "The diet plan has been successfully restored."}, status=status.HTTP_200_OK)
        except DietRecommendation.DoesNotExist:
            return Response({'error': 'Diet plan not found.'}, status=status.HTTP_404_NOT_FOUND)


# ==============================================================================
# Nutritionist — AI Plan Generation
# ==============================================================================

class GeneratePlanForPatientView(APIView):
    permission_classes = [
        permissions.IsAuthenticated,
        IsNutritionist,
        IsVerifiedNutritionist
    ]

    def post(self, request, patient_id):
        from subscriptions.permissions import check_nutritionist_feature
        allowed, err_msg, plan_name = check_nutritionist_feature(request.user, "nutri_ai_diet_allowed")
        if not allowed:
            return Response({
                "error": err_msg,
                "detail": err_msg,
                "upgrade_required": True,
                "feature": "nutri_ai_diet_allowed",
                "current_plan": plan_name
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            patient = User.objects.get(id=patient_id, role="user")
        except User.DoesNotExist:
            return Response({"error": "Patient not found."}, status=404)

        if not PatientAssignment.objects.filter(nutritionist=request.user, patient=patient).exists():
            return Response({"error": "Not assigned."}, status=403)

        try:
            check_patient_ai_diet_access(patient)
        except Exception as e:
            return Response({"error": str(e)}, status=403)

        if DietRecommendation.objects.filter(user=patient, status__in=["pending", "generating"]).exists():
            return Response({"error": "Plan already generating or pending."}, status=409)

        placeholder = DietRecommendation.objects.create(
            user=patient,
            for_week_starting=timezone.now().date(),
            meals={},
            original_ai_plan={},
            status="generating",
            reviewed_by=request.user
        )

        executor.submit(self._generate_and_finalize_plan, placeholder.id, request.user.id)

        serializer = DietRecommendationSerializer(placeholder)
        return Response(serializer.data, status=201)

    def _generate_and_finalize_plan(self, plan_id, nutritionist_id):
        try:
            plan = DietRecommendation.objects.get(id=plan_id)
            patient = plan.user

            profile = UserProfile.objects.get(user=patient)
            report = LabReport.objects.filter(user=patient).order_by("-report_date").first()

            profile_dict = _serialize_user_profile(profile)
            report_dict = _serialize_lab_report(report)
            targets_dict = _calculate_target_nutrients(profile_dict)

            plan_json, error = generate_ai_plan_for_patient(profile_dict, report_dict, targets_dict)

            if error:
                plan.status = "failed"
                plan.save(update_fields=["status"])
                return

            plan.meals = plan_json
            plan.original_ai_plan = plan_json
            plan.status = "pending"
            plan.save(update_fields=["meals", "original_ai_plan", "status"])

        except Exception as e:
            print("Background AI Error:", e)
            try:
                plan = DietRecommendation.objects.get(id=plan_id)
                plan.status = "failed"
                plan.save(update_fields=["status"])
            except Exception:
                pass


# ==============================================================================
# Patient Views
# ==============================================================================

class MyAssignedNutritionistView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPatient]

    def get(self, request, *args, **kwargs):
        try:
            assignment = PatientAssignment.objects.get(patient=request.user)
            serializer = UserSerializer1(assignment.nutritionist)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except PatientAssignment.DoesNotExist:
            return Response(
                {'error': 'You have not been assigned a nutritionist yet.'},
                status=status.HTTP_404_NOT_FOUND
            )


from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

class NutritionistSelfProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        user = request.user
        nutri_profile, _ = NutritionistProfile.objects.get_or_create(user=user)
        user_profile = UserProfile.objects.filter(user=user).first()

        assigned_patients_count = PatientAssignment.objects.filter(nutritionist=user).count()
        from django.db.models import Count, Q
        diet_stats = DietRecommendation.objects.filter(reviewed_by=user).aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(status="approved", is_deleted=False))
        )
        total_diet_plans = diet_stats['total']
        active_diet_plans = diet_stats['active']

        sub = UserSubscription.objects.filter(user=user, is_active=True).select_related("plan").order_by("-created_at").first()
        sub_data = None
        if sub:
            rem_days = max(0, (sub.end_date - timezone.now().date()).days) if sub.end_date else 0
            is_valid = sub.is_active and (sub.end_date >= timezone.now().date() if sub.end_date else True)
            sub_data = {
                "has_plan": True,
                "plan_name": sub.plan.name if sub.plan else "Active Plan",
                "price": sub.plan.price if sub.plan else 0,
                "duration_days": sub.plan.duration_days if sub.plan else 30,
                "start_date": sub.start_date,
                "expires_at": sub.end_date,
                "remaining_days": rem_days,
                "is_active": is_valid,
            }
        else:
            sub_data = {
                "has_plan": False,
                "plan_name": "No Active Subscription",
                "price": 0,
                "duration_days": 0,
                "start_date": None,
                "expires_at": None,
                "remaining_days": 0,
                "is_active": False,
            }

        return Response({
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "phone_number": user.phone_number or "",
                "role": user.role,
                "date_joined": user.date_joined,
                "is_active": user.is_active,
            },
            "nutritionist_profile": {
                "nutritionist_type": nutri_profile.nutritionist_type,
                "is_virtual_enabled": nutri_profile.is_virtual_enabled,
                "is_verified": nutri_profile.is_verified,
                "verified_at": nutri_profile.verified_at,
                "professional_title": nutri_profile.professional_title or "Clinical Nutritionist",
                "qualification": nutri_profile.qualification or "",
                "registration_number": nutri_profile.registration_number or "",
                "issuing_authority": nutri_profile.issuing_authority or "",
                "years_of_experience": nutri_profile.years_of_experience or 0,
                "current_organization": nutri_profile.current_organization or "",
                "professional_bio": nutri_profile.professional_bio or "",
                "languages_spoken": nutri_profile.languages_spoken if isinstance(nutri_profile.languages_spoken, list) else [],
                "specializations": nutri_profile.specializations if isinstance(nutri_profile.specializations, list) else [],
                "is_online_available": nutri_profile.is_online_available,
                "is_offline_available": nutri_profile.is_offline_available,
                "offline_location": nutri_profile.offline_location or "",
                "online_price": nutri_profile.online_price,
                "offline_price": nutri_profile.offline_price,
                "offline_payment_required": nutri_profile.offline_payment_required,
                "pending_online_price": nutri_profile.pending_online_price,
                "pending_offline_price": nutri_profile.pending_offline_price,
                "pending_offline_payment_required": nutri_profile.pending_offline_payment_required,
                "price_approval_status": nutri_profile.price_approval_status,
                "price_rejection_reason": nutri_profile.price_rejection_reason or "",
                "qualification_certificate": nutri_profile.qualification_certificate.url if nutri_profile.qualification_certificate else None,
                "registration_certificate": nutri_profile.registration_certificate.url if nutri_profile.registration_certificate else None,
                "government_id": nutri_profile.government_id.url if nutri_profile.government_id else None,
                "experience_certificate": nutri_profile.experience_certificate.url if nutri_profile.experience_certificate else None,
                "additional_certifications": nutri_profile.additional_certifications.url if nutri_profile.additional_certifications else None,
                "profile_photo": nutri_profile.profile_photo.url if nutri_profile.profile_photo else None,
            },
            "contact_details": {
                "mobile_number": user_profile.mobile_number if user_profile else (user.phone_number or ""),
                "gender": user_profile.gender if user_profile else "",
                "date_of_birth": user_profile.date_of_birth if user_profile else None,
                "city": user_profile.city if user_profile else "",
                "country": user_profile.country if user_profile else "",
            },
            "practice_metrics": {
                "assigned_patients_count": assigned_patients_count,
                "total_diet_plans": total_diet_plans,
                "active_diet_plans": active_diet_plans,
            },
            "subscription": sub_data,
        }, status=status.HTTP_200_OK)

    def patch(self, request):
        user = request.user
        data = request.data

        # Update User model
        user_fields_to_update = []
        if "full_name" in data and data.get("full_name") is not None:
            user.full_name = str(data.get("full_name")).strip()
            user_fields_to_update.append("full_name")
        if "phone_number" in data and data.get("phone_number") is not None:
            user.phone_number = str(data.get("phone_number")).strip()
            user_fields_to_update.append("phone_number")

        if user_fields_to_update:
            user.save(update_fields=user_fields_to_update)

        # Update or create UserProfile
        user_profile, _ = UserProfile.objects.get_or_create(user=user)
        if "mobile_number" in data:
            user_profile.mobile_number = str(data.get("mobile_number") or "").strip()
        elif "phone_number" in data:
            user_profile.mobile_number = str(data.get("phone_number") or "").strip()

        if "gender" in data:
            user_profile.gender = str(data.get("gender") or "").strip()
        if "date_of_birth" in data:
            dob_raw = data.get("date_of_birth")
            user_profile.date_of_birth = parse_date(str(dob_raw)) if dob_raw else None
        if "city" in data:
            user_profile.city = str(data.get("city") or "").strip()
        if "country" in data:
            user_profile.country = str(data.get("country") or "").strip()
        user_profile.save()

        # Update NutritionistProfile
        nutri_profile, _ = NutritionistProfile.objects.get_or_create(user=user)
        nutri_fields_to_update = []

        # Professional info
        if "professional_title" in data:
            nutri_profile.professional_title = str(data.get("professional_title") or "").strip()
            nutri_fields_to_update.append("professional_title")
        if "qualification" in data:
            nutri_profile.qualification = str(data.get("qualification") or "").strip()
            nutri_fields_to_update.append("qualification")
        if "registration_number" in data:
            nutri_profile.registration_number = str(data.get("registration_number") or "").strip()
            nutri_fields_to_update.append("registration_number")
        if "issuing_authority" in data:
            nutri_profile.issuing_authority = str(data.get("issuing_authority") or "").strip()
            nutri_fields_to_update.append("issuing_authority")
        if "years_of_experience" in data:
            try:
                nutri_profile.years_of_experience = int(data.get("years_of_experience") or 0)
                nutri_fields_to_update.append("years_of_experience")
            except (ValueError, TypeError):
                pass
        if "current_organization" in data:
            nutri_profile.current_organization = str(data.get("current_organization") or "").strip()
            nutri_fields_to_update.append("current_organization")
        if "professional_bio" in data:
            nutri_profile.professional_bio = str(data.get("professional_bio") or "").strip()
            nutri_fields_to_update.append("professional_bio")

        # Languages Spoken (Handle string or JSON list)
        if "languages_spoken" in data:
            val = data.get("languages_spoken")
            if isinstance(val, str):
                import json
                try:
                    nutri_profile.languages_spoken = json.loads(val)
                except Exception:
                    nutri_profile.languages_spoken = [l.strip() for l in val.split(",") if l.strip()]
            elif isinstance(val, list):
                nutri_profile.languages_spoken = val
            nutri_fields_to_update.append("languages_spoken")

        # Specializations (Handle string or JSON list)
        if "specializations" in data:
            val = data.get("specializations")
            if isinstance(val, str):
                import json
                try:
                    nutri_profile.specializations = json.loads(val)
                except Exception:
                    nutri_profile.specializations = [s.strip() for s in val.split(",") if s.strip()]
            elif isinstance(val, list):
                nutri_profile.specializations = val
            nutri_fields_to_update.append("specializations")

        # Availability & Location
        if "is_virtual_enabled" in data:
            val = data.get("is_virtual_enabled")
            nutri_profile.is_virtual_enabled = val in [True, "true", "True", 1, "1"]
            nutri_fields_to_update.append("is_virtual_enabled")
        if "is_online_available" in data:
            val = data.get("is_online_available")
            nutri_profile.is_online_available = val in [True, "true", "True", 1, "1"]
            nutri_fields_to_update.append("is_online_available")
        if "is_offline_available" in data:
            val = data.get("is_offline_available")
            nutri_profile.is_offline_available = val in [True, "true", "True", 1, "1"]
            nutri_fields_to_update.append("is_offline_available")
        if "offline_location" in data:
            nutri_profile.offline_location = str(data.get("offline_location") or "").strip()
            nutri_fields_to_update.append("offline_location")

        # Handle Document & File Attachments (from request.FILES or request.data)
        file_fields = [
            "qualification_certificate",
            "registration_certificate",
            "government_id",
            "experience_certificate",
            "additional_certifications",
            "profile_photo",
        ]
        has_file_uploaded = False
        for f_name in file_fields:
            if f_name in request.FILES:
                setattr(nutri_profile, f_name, request.FILES[f_name])
                nutri_fields_to_update.append(f_name)
                has_file_uploaded = True
            elif f_name in request.data and hasattr(request.data[f_name], 'read'):
                setattr(nutri_profile, f_name, request.data[f_name])
                nutri_fields_to_update.append(f_name)
                has_file_uploaded = True

        # Handle Price Updates (Requires Admin Approval)
        price_requested = False
        if "online_price" in data and data.get("online_price") not in [None, ""]:
            try:
                nutri_profile.pending_online_price = float(data.get("online_price"))
                price_requested = True
            except (ValueError, TypeError):
                pass
        if "offline_price" in data and data.get("offline_price") not in [None, ""]:
            try:
                nutri_profile.pending_offline_price = float(data.get("offline_price"))
                price_requested = True
            except (ValueError, TypeError):
                pass
        if "offline_payment_required" in data and data.get("offline_payment_required") not in [None, ""]:
            val = data.get("offline_payment_required")
            nutri_profile.pending_offline_payment_required = val in [True, "true", "True", 1, "1"]
            price_requested = True

        if price_requested:
            nutri_profile.price_approval_status = "pending"
            nutri_profile.price_rejection_reason = None
            nutri_fields_to_update.extend([
                "pending_online_price",
                "pending_offline_price",
                "pending_offline_payment_required",
                "price_approval_status",
                "price_rejection_reason"
            ])

        if has_file_uploaded:
            nutri_profile.save()
        elif nutri_fields_to_update:
            nutri_profile.save(update_fields=list(set(nutri_fields_to_update)))

        msg = "Profile updated successfully."
        if price_requested:
            msg += " Your requested price changes have been submitted for Admin approval."

        return Response({"message": msg}, status=status.HTTP_200_OK)


class AdminNutritionistPricingListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not (request.user.is_admin or request.user.role in ['admin', 'owner']):
            return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

        status_filter = request.query_params.get("status", "pending")
        queryset = NutritionistProfile.objects.select_related("user").all()

        if status_filter != "all":
            queryset = queryset.filter(price_approval_status=status_filter)

        data = []
        for profile in queryset:
            data.append({
                "id": profile.id,
                "user_id": profile.user.id,
                "email": profile.user.email,
                "full_name": profile.user.full_name,
                "is_online_available": profile.is_online_available,
                "is_offline_available": profile.is_offline_available,
                "offline_location": profile.offline_location,
                "current_online_price": profile.online_price,
                "current_offline_price": profile.offline_price,
                "current_offline_payment_required": profile.offline_payment_required,
                "pending_online_price": profile.pending_online_price,
                "pending_offline_price": profile.pending_offline_price,
                "pending_offline_payment_required": profile.pending_offline_payment_required,
                "price_approval_status": profile.price_approval_status,
                "price_rejection_reason": profile.price_rejection_reason,
            })

        return Response(data, status=status.HTTP_200_OK)


class AdminNutritionistPricingApproveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, profile_id):
        if not (request.user.is_admin or request.user.role in ['admin', 'owner']):
            return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

        try:
            profile = NutritionistProfile.objects.select_related("user").get(id=profile_id)
        except NutritionistProfile.DoesNotExist:
            return Response({"detail": "Nutritionist profile not found."}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get("action") # 'approve' or 'reject'
        reason = request.data.get("reason", "")

        from features.models import Message
        from features.tasks import send_message_notification

        if action == "approve":
            if profile.pending_online_price is not None:
                profile.online_price = profile.pending_online_price
            if profile.pending_offline_price is not None:
                profile.offline_price = profile.pending_offline_price
            if profile.pending_offline_payment_required is not None:
                profile.offline_payment_required = profile.pending_offline_payment_required

            profile.pending_online_price = None
            profile.pending_offline_price = None
            profile.pending_offline_payment_required = None
            profile.price_approval_status = "approved"
            profile.price_rejection_reason = None
            profile.save()

            # Create notification message for nutritionist
            msg_text = (
                f"🎉 Your appointment pricing has been APPROVED by Admin! "
                f"Online Price: ₹{profile.online_price}, Offline Price: ₹{profile.offline_price}."
            )
            message_obj = Message.objects.create(
                sender=request.user,
                receiver=profile.user,
                text=msg_text
            )
            try:
                send_message_notification(message_obj)
            except Exception as e:
                print(f"Failed to trigger WebSocket notification: {e}")

            return Response({"message": "Pricing approved successfully and nutritionist notified."}, status=status.HTTP_200_OK)

        elif action == "reject":
            profile.price_approval_status = "rejected"
            profile.price_rejection_reason = reason
            profile.pending_online_price = None
            profile.pending_offline_price = None
            profile.pending_offline_payment_required = None
            profile.save()

            # Create notification message for nutritionist
            msg_text = f"⚠️ Your appointment pricing request was REJECTED by Admin. Reason: {reason or 'Not specified'}"
            message_obj = Message.objects.create(
                sender=request.user,
                receiver=profile.user,
                text=msg_text
            )
            try:
                send_message_notification(message_obj)
            except Exception as e:
                print(f"Failed to trigger WebSocket notification: {e}")

            return Response({"message": "Pricing rejected and nutritionist notified."}, status=status.HTTP_200_OK)

        else:
            return Response({"detail": "Invalid action. Use 'approve' or 'reject'."}, status=status.HTTP_400_BAD_REQUEST)


class NutritionistChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        if not old_password or not new_password or not confirm_password:
            return Response(
                {"error": "Current password, new password, and confirmation are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.check_password(old_password):
            return Response(
                {"error": "Incorrect current password."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if new_password != confirm_password:
            return Response(
                {"error": "New password and confirmation do not match."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(new_password) < 8:
            return Response(
                {"error": "Password must be at least 8 characters long."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if old_password == new_password:
            return Response(
                {"error": "New password must be different from current password."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save()

        return Response(
            {"message": "Your password has been changed successfully."},
            status=status.HTTP_200_OK
        )


class AdminNutritionistVerifyView(APIView):
    """
    Admin-only endpoint to verify or unverify a nutritionist.
    Creates a persistent Message in the database, sends email & WebSocket push.
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, profile_id):
        from features.models import Message
        from features.tasks import send_message_notification

        profile = get_object_or_404(NutritionistProfile, id=profile_id)
        action = request.data.get("action", "verify")  # "verify" or "unverify"

        if action == "verify":
            profile.is_verified = True
            profile.verified_at = timezone.now()
            profile.save()

            msg_text = (
                "🎉 Congratulations! Your practitioner profile has been officially VERIFIED & APPROVED by TrackIntake Admin. "
                "Your clinical credentials and consultation services are now active and live for patients."
            )
            message_obj = Message.objects.create(
                sender=request.user,
                receiver=profile.user,
                text=msg_text
            )
            try:
                send_message_notification(message_obj)
            except Exception as e:
                print(f"Failed to trigger verification notification: {e}")

            return Response({"message": "Nutritionist verified successfully and notification dispatched."}, status=status.HTTP_200_OK)

        elif action == "unverify":
            profile.is_verified = False
            profile.verified_at = None
            profile.save()

            msg_text = (
                "⚠️ Your practitioner account verification status has been revoked by Admin. "
                "Please check your uploaded verification documents or contact support."
            )
            message_obj = Message.objects.create(
                sender=request.user,
                receiver=profile.user,
                text=msg_text
            )
            try:
                send_message_notification(message_obj)
            except Exception as e:
                print(f"Failed to trigger unverify notification: {e}")

            return Response({"message": "Nutritionist unverified and notification dispatched."}, status=status.HTTP_200_OK)

        else:
            return Response({"detail": "Invalid action. Use 'verify' or 'unverify'."}, status=status.HTTP_400_BAD_REQUEST)