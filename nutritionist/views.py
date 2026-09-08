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

from subscriptions.models import Plan
from subscriptions.services import activate_plan_for_user, check_patient_ai_diet_access

from nutritionist.models import PatientAssignment
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
        return User.objects.filter(role='user').order_by('-date_joined')


class AssignPatientAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]

    def post(self, request, *args, **kwargs):
        patient_id = request.data.get('patient_id')
        if not patient_id:
            return Response({'error': 'patient_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

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
        return User.objects.filter(id__in=assigned_patient_ids)


class NutritionistCreatePatientView(generics.GenericAPIView):
    serializer_class = CreatePatientSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if request.user.role != "nutritionist":
            return Response({"detail": "Only nutritionists can create patients."}, status=403)

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
            user_profile = UserProfile.objects.get(user_id=patient_id)
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
        return UserMeal.objects.filter(user_id=patient_id).order_by('-consumed_at')


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
        return DietRecommendation.objects.filter(user_id=patient_id).order_by('-created_at')


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
        return DietRecommendation.objects.filter(user_id__in=assigned_patient_ids)


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
        notes = request.data.get("notes", "")
        approved_for_retraining = request.data.get("approved_for_retraining", False)

        if not isinstance(approved_for_retraining, bool):
            return Response({'error': '"approved_for_retraining" must be a boolean.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            recommendation = DietRecommendation.objects.get(id=plan_id)
            recommendation.nutritionist_retraining_notes = notes
            recommendation.approved_for_retraining = approved_for_retraining
            recommendation.save()
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


class ArchiveDietPlanView(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]
    serializer_class = DietRecommendationSerializer

    def get_queryset(self):
        assigned_patient_ids = PatientAssignment.objects.filter(
            nutritionist=self.request.user
        ).values_list('patient_id', flat=True)
        return DietRecommendation.objects.filter(user_id__in=assigned_patient_ids, is_deleted=False)

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted', 'updated_at'])
        return Response({"message": "The diet plan has been successfully archived."}, status=status.HTTP_200_OK)


class RestoreDietPlanView(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]
    serializer_class = DietRecommendationSerializer

    def get_queryset(self):
        assigned_patient_ids = PatientAssignment.objects.filter(
            nutritionist=self.request.user
        ).values_list('patient_id', flat=True)
        return DietRecommendation.objects.filter(user_id__in=assigned_patient_ids, is_deleted=True)

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = False
        instance.save(update_fields=['is_deleted', 'updated_at'])
        return Response({"message": "The diet plan has been successfully restored."}, status=status.HTTP_200_OK)


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