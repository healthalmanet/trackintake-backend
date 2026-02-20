from datetime import date
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
import datetime
import time
from django.shortcuts import render
import copy # Don't forget this import
import numpy as np
from rest_framework.exceptions import NotFound
from rest_framework import generics, permissions, status, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Sum
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from datetime import datetime, time
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db import transaction
from django.utils.dateparse import parse_date
from django.utils.timezone import now
from datetime import date
from django.db.models.functions import Length
import numpy as np
from django.contrib.auth import get_user_model
from rest_framework.permissions import IsAuthenticated
from django.contrib.postgres.search import TrigramSimilarity # Make sure you have the pg_trgm extension enabled
from nutritionist.permissions import IsVerifiedNutritionist
from concurrent.futures import ThreadPoolExecutor

from rest_framework.views import APIView
from rest_framework import permissions, status
from rest_framework.response import Response

from subscriptions.services import check_patient_ai_diet_access
from nutritionist.models import PatientAssignment
from diet.models import DietRecommendation
from userProfile.models import UserProfile
from user.models import User
from diet.serializers import DietRecommendationSerializer
from utils.generative import generate_ai_plan_for_patient

import asyncio
import threading # <-- Use the standard threading library
import traceback
import numpy as np
from diet.tasks import generate_ai_diet_task
from django.utils import timezone



from diet.serializers import DietRecommendationSerializer
from ml_model.src.generator import generate_diet_plan
from utils.gemini import fetch_nutrition_from_gemini, food_search_gemini
from utils.pagination import StandardResultsSetPagination


from .models import PatientAssignment
from diet.models import DietRecommendation
from user.models import User
from userProfile.models import LabReport, UserProfile
from userFood.models import FoodItem, UserMeal
from .serializers import (
    CreatePatientSerializer, DietRecommendationDetailSerializer, UserSerializer1, PatientProfileSerializer1,
    UserMealSerializer1, DietRecommendationWithPatientSerializer1,
    ) 
from userProfile.serializers import LabReportSerializer, UserProfileSerializer
from django.db import transaction

from utils.generative import generate_ai_plan_for_patient
from utils.generative import (
    generate_ai_plan_for_patient,
    _serialize_user_profile,
    _serialize_lab_report,
    _calculate_target_nutrients,
)
User = get_user_model()



executor = ThreadPoolExecutor(max_workers=2)

# Create your views here.
###############################################################################DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD
# --- Permission Class ---
class IsNutritionist(permissions.BasePermission):
    """
    Allows access only to authenticated users with the 'nutritionist' role.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'nutritionist'


# --- API Views ---

class UserListForNutritionistView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]
    serializer_class = UserSerializer1
    # pagination_class = StandardResultsSetPagination # Uncomment if you have this
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['email', 'full_name']
    ordering_fields = ['date_joined', 'full_name']
    
    def get_queryset(self):
        # ✅ IMPROVEMENT: Only show users with the 'user' role (patients).
        return User.objects.filter(role='user').order_by('-date_joined')


class AssignPatientAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]

    def post(self, request, *args, **kwargs):
        patient_id = request.data.get('patient_id')
        if not patient_id:
            return Response({'error': 'patient_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Ensure the user being assigned is actually a patient
            patient = User.objects.get(id=patient_id, role='user')
            # get_or_create prevents duplicate assignments
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
    filterset_fields = ['email']  # exact match for email
    search_fields = ['full_name']  # partial match for name

    def get_queryset(self):
        assigned_patient_ids = PatientAssignment.objects.filter(
            nutritionist=self.request.user
        ).values_list('patient_id', flat=True)

        return User.objects.filter(id__in=assigned_patient_ids)


# ✅ FIXED: This view is completely rewritten to use the correct models.





class PatientProfileDetailView(APIView):
    """
    Handles retrieving and updating a specific patient's profile.
    This single API endpoint handles both GET and PUT requests.
    """
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]

    class PatientProfileSerializer1(serializers.ModelSerializer):
        """
        Serializer for the UserProfile model, designed for nutritionist view.
        """
        email = serializers.EmailField(source='user.email', read_only=True)
        full_name = serializers.CharField(source='user.full_name', read_only=True)
        bmi = serializers.FloatField(read_only=True) # Expose the BMI property

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
        """
        Retrieves the patient's profile and latest lab report.
        Handles cases where no lab report exists without returning an error.
        """
        if not PatientAssignment.objects.filter(nutritionist=request.user, patient_id=patient_id).exists():
            return Response({'error': 'You are not assigned to this patient.'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            user_profile = UserProfile.objects.get(user_id=patient_id)
            profile_serializer = self.PatientProfileSerializer1(user_profile)

            # --- THE FIX IS HERE ---
            # 1. Initialize lab report data as None.
            lab_report_data = None
            
            # 2. Try to get the latest lab report object.
            latest_lab_report = LabReport.objects.filter(user_id=patient_id).order_by('-report_date').first()
            
            # 3. Only if the object exists, serialize it and get its .data.
            if latest_lab_report:
                lab_report_data = LabReportSerializer(latest_lab_report).data
            # --- END OF FIX ---
            
            # Now, the response is built safely.
            return Response({
                'profile': profile_serializer.data,
                'latest_lab_report': lab_report_data  # This is either the serialized data or None
            }, status=status.HTTP_200_OK)
            
        except UserProfile.DoesNotExist:
            return Response({'error': 'Patient profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        
    def put(self, request, patient_id):
        """
        Updates the patient's profile data.
        """
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











# ✅ NEW: Implementation for the previously empty PatientMealLogView.
class PatientMealLogView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]
    serializer_class = UserMealSerializer1
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['consumed_at','date']  # ✅ Filter by exact date
    ordering_fields = ['consumed_at']
    ordering = ['-consumed_at']

    def get_queryset(self):
        patient_id = self.kwargs['patient_id']
        if not PatientAssignment.objects.filter(nutritionist=self.request.user, patient_id=patient_id).exists():
            raise PermissionDenied("You are not assigned to this patient.")
        return UserMeal.objects.filter(user_id=patient_id).order_by('-consumed_at')



class NutritionistPatientDietRecommendationsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]
    serializer_class = DietRecommendationWithPatientSerializer1

    def get_queryset(self):
        patient_id = self.kwargs['patient_id']
        if not PatientAssignment.objects.filter(nutritionist=self.request.user, patient_id=patient_id).exists():
            raise PermissionDenied("You are not assigned to this patient.")
        return DietRecommendation.objects.filter(user_id=patient_id).order_by('-created_at')


class ApproveOrRejectDietView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]

    def post(self, request, pk):
        action = request.data.get("action")
        comment = request.data.get("comment", "")

        if action not in ["approved", "rejected"]:
            return Response({'error': 'Invalid action. Use "approved" or "rejected".'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            recommendation = DietRecommendation.objects.get(id=pk)
            
            # Optional: Check if this nutritionist is assigned to the recommendation's user
            if not PatientAssignment.objects.filter(nutritionist=request.user, patient=recommendation.user).exists():
                 return Response({'error': 'You are not assigned to this patient.'}, status=status.HTTP_403_FORBIDDEN)

            recommendation.status = action
            recommendation.reviewed_by = request.user
            recommendation.nutritionist_comment = comment
            recommendation.save()

            return Response({'message': f'Diet plan has been {action}.'}, status=status.HTTP_200_OK)
        except DietRecommendation.DoesNotExist:
            return Response({'error': 'Recommendation not found'}, status=status.HTTP_404_NOT_FOUND)


# ✅ FIXED: This view is rewritten to update the existing DietRecommendation model.
class UpdateRetrainingFlagsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]

    def post(self, request, recommendation_id):
        # Get data from request
        notes = request.data.get("notes", "")
        approved_for_retraining = request.data.get("approved_for_retraining", False)
        
        # Ensure 'approved_for_retraining' is a boolean
        if not isinstance(approved_for_retraining, bool):
            return Response({'error': '"approved_for_retraining" must be a boolean (true/false).'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            recommendation = DietRecommendation.objects.get(id=recommendation_id)
            
            # Update the fields directly on the DietRecommendation instance
            recommendation.nutritionist_retraining_notes = notes
            recommendation.approved_for_retraining = approved_for_retraining
            recommendation.save()
            
            return Response({'message': 'Retraining feedback submitted successfully.'}, status=status.HTTP_200_OK)
        except DietRecommendation.DoesNotExist:
            return Response({'error': 'Recommendation not found.'}, status=status.HTTP_404_NOT_FOUND)





FUZZY_MATCH_THRESHOLD = 0.9

#WORKINGd

class EditDietPlanView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]
    serializer_class = DietRecommendationDetailSerializer
    queryset = DietRecommendation.objects.select_related('user', 'reviewed_by').all()

          
# NEW, CORRECTED VERSION
    def _get_or_create_food_item(self, food_name: str) -> FoodItem | None:
        """
        Finds a food item locally or calls Gemini, ensuring the user's original
        food name is preserved.
        """
        original_food_name = food_name.strip()
        if not original_food_name:
            return None
    
        # 1. Exact match (fastest and most accurate)
        food = FoodItem.objects.filter(name__iexact=original_food_name).first()
        if food:
            print(f"✅ DB HIT (Exact): Found '{food.name}' for query '{original_food_name}'")
            return food
    
        # 2. Conditional Fuzzy Match
        if len(original_food_name.split()) > 1:
            food = FoodItem.objects.annotate(
                similarity=TrigramSimilarity('name', original_food_name)
            ).filter(similarity__gt=FUZZY_MATCH_THRESHOLD).order_by('-similarity').first()
            if food:
                print(f"✅ DB HIT (Fuzzy): Found '{food.name}' for query '{original_food_name}'")
                return food
    
        # 3. Gemini fallback with name preservation
        print(f"🔥 API CALL: No local match for '{original_food_name}'. Calling Gemini.")
        try:
            # This assumes food_search_gemini returns a saved FoodItem object
            gemini_food_item = food_search_gemini(original_food_name)
            if not gemini_food_item:
                return None
    
            # --- THE CORE FIX ---
            # If Gemini returned a different, normalized name (e.g., "Water"),
            # we correct it to match the nutritionist's input (e.g., "Warm Water").
            if gemini_food_item.name.lower() != original_food_name.lower():
                # Check if an item with the desired name already exists to avoid errors
                existing_food = FoodItem.objects.filter(name__iexact=original_food_name).first()
                if existing_food:
                    # If it exists, use it, and delete the one Gemini just created.
                    gemini_food_item.delete() 
                    return existing_food
                else:
                    # Otherwise, rename the item Gemini gave us and save it.
                    gemini_food_item.name = original_food_name
                    gemini_food_item.save()
            
            return gemini_food_item
    
        except Exception as e:
            print(f"❌ EXCEPTION: Error processing '{original_food_name}': {e}")
            return None

    



    def _format_food_for_plan(self, food: FoodItem) -> dict:
        """
        (THIS METHOD IS UNCHANGED)
        Formats a FoodItem instance into the dictionary structure needed for the plan's JSONField.
        """
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
    def patch(self, request, recommendation_id):
        #
        # THIS ENTIRE METHOD IS IDENTICAL TO YOUR ORIGINAL CODE.
        # NO CHANGES HAVE BEEN MADE HERE.
        #
        try:
            # Use select_for_update to lock the row and prevent race conditions.
            recommendation = DietRecommendation.objects.select_for_update().get(pk=recommendation_id)
        except DietRecommendation.DoesNotExist:
            return Response({'error': 'Recommendation not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Process meal updates
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

                    # This now correctly returns a FoodItem instance or None
                    food_item_obj = self._get_or_create_food_item(food_name)
                    
                    if food_item_obj:
                        db_meals[existing_key][meal_slot] = self._format_food_for_plan(food_item_obj)
                    else:
                        # If the food could not be found or created, remove it from the plan
                        db_meals[existing_key].pop(meal_slot, None)
            
            recommendation.meals = db_meals

        # Build list of fields to update for an efficient save()
        update_fields = ['meals', 'updated_at']

        # Process other potential fields from the request
        if 'nutritionist_comment' in request.data:
            recommendation.nutritionist_comment = request.data['nutritionist_comment']
            update_fields.append('nutritionist_comment')

        if 'status' in request.data:
            recommendation.status = request.data['status']
            update_fields.append('status')
        elif new_meals_data: # Automatically set to pending if meals were edited
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

        # Serialize the final, updated instance for the response
        serializer = self.get_serializer(recommendation)
        return Response({
            'message': 'Diet plan updated successfully.',
            'data': serializer.data
        }, status=status.HTTP_200_OK)










# ==============================================================================
# 🔹 NEW API VIEW: List all diet plans for all assigned patients
# ==============================================================================
class AllAssignedDietPlansListView(generics.ListAPIView):
    """
    Provides a list of all diet recommendations for all patients
    assigned to the currently authenticated nutritionist.

    Supports filtering by status, and searching by patient's name or email.
    - `?status=pending`
    - `?status=approved`
    - `?search=Anjali`
    """
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]
    serializer_class = DietRecommendationWithPatientSerializer1
    pagination_class = StandardResultsSetPagination # Optional: uncomment if you have pagination
    
    # Enable filtering and searching
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    # Fields for filtering (e.g., /.../?status=pending)
    filterset_fields = ['status']
    
    # Fields for searching (e.g., /.../?search=Sharma)
    # Note the double-underscore to search on the related User model
    search_fields = ['user__full_name', 'user__email']
    
    # Fields for ordering (e.g., /.../?ordering=-created_at)
    ordering_fields = ['created_at', 'for_week_starting']
    ordering = ['-created_at'] # Default ordering

    def get_queryset(self):
        """
        This method customizes the queryset to only return diet plans
        for patients assigned to the logged-in nutritionist.
        """
        # 1. Get the list of patient IDs assigned to this nutritionist
        assigned_patient_ids = PatientAssignment.objects.filter(
            nutritionist=self.request.user
        ).values_list('patient_id', flat=True)

        # 2. Filter the DietRecommendation objects to only include those
        #    belonging to the list of assigned patient IDs.
        queryset = DietRecommendation.objects.filter(user_id__in=assigned_patient_ids)

        return queryset
    

#Create Patient
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
                PatientAssignment.objects.create(nutritionist=request.user, patient=user)
                return Response({"detail": "Patient created and assigned successfully."}, status=201)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)


from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=2)

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

        if not PatientAssignment.objects.filter(
            nutritionist=request.user,
            patient=patient
        ).exists():
            return Response({"error": "Not assigned."}, status=403)

        try:
            check_patient_ai_diet_access(patient)
        except Exception as e:
            return Response({"error": str(e)}, status=403)

        if DietRecommendation.objects.filter(
            user=patient,
            status__in=["pending", "generating"]
        ).exists():
            return Response(
                {"error": "Plan already generating or pending."},
                status=409
            )

        # ✅ Create placeholder immediately
        placeholder = DietRecommendation.objects.create(
            user=patient,
            for_week_starting=timezone.now().date(),
            meals={},
            original_ai_plan={},
            status="generating",
            reviewed_by=request.user
        )

        # ✅ Run AI in background
        executor.submit(
            self._generate_and_finalize_plan,
            placeholder.id,
            request.user.id
        )

        serializer = DietRecommendationSerializer(placeholder)
        return Response(serializer.data, status=201)

    def _generate_and_finalize_plan(self, plan_id, nutritionist_id):

        try:
            plan = DietRecommendation.objects.get(id=plan_id)
            patient = plan.user

            # 🔹 Fetch profile & report
            profile = UserProfile.objects.get(user=patient)
            report = (
                LabReport.objects
                .filter(user=patient)
                .order_by("-report_date")
                .first()
            )

            # 🔹 Serialize
            profile_dict = _serialize_user_profile(profile)
            report_dict = _serialize_lab_report(report)
            targets_dict = _calculate_target_nutrients(profile_dict)

            # 🔹 PURE AI call
            plan_json, error = generate_ai_plan_for_patient(
                profile_dict,
                report_dict,
                targets_dict
            )

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












# class GeneratePlanForPatientView(APIView):
#     """
#     AI Diet generation endpoint.
#     Restriction is based on PATIENT subscription, not nutritionist.
#     """
#     permission_classes = [permissions.IsAuthenticated, IsNutritionist]

#     def post(self, request, patient_id, *args, **kwargs):

#         # 1️⃣ Validate patient
#         try:
#             patient = User.objects.get(id=patient_id, role="user")
#         except User.DoesNotExist:
#             return Response(
#                 {"error": "Patient not found."},
#                 status=status.HTTP_404_NOT_FOUND
#             )

#         # 2️⃣ Nutritionist must be assigned
#         if not PatientAssignment.objects.filter(
#             nutritionist=request.user,
#             patient=patient
#         ).exists():
#             return Response(
#                 {"error": "You are not assigned to this patient."},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         # 🔒 3️⃣ AI DIET RESTRICTION (CORE LOGIC)
#         check_patient_ai_diet_access(patient)

#         # 4️⃣ Existing business validations
#         if DietRecommendation.objects.filter(
#             user=patient,
#             status="pending"
#         ).exists():
#             return Response(
#                 {"error": "This patient already has a plan pending review."},
#                 status=status.HTTP_409_CONFLICT
#             )

#         if not UserProfile.objects.filter(user=patient).exists():
#             return Response(
#                 {"error": "Patient profile must be completed first."},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         # 5️⃣ Generate AI plan
#         # new_plan, error = generate_ai_plan_for_patient(
#         #     patient_id=patient.id,
#         #     nutritionist_id=request.user.id
#         # )
#         # 🚫 Block duplicates
#         if DietRecommendation.objects.filter(
#             user=patient,
#             status__in=["generating", "pending"]
#         ).exists():
#             return Response(
#                 {"error": "Plan already generating or pending."},
#                 status=status.HTTP_409_CONFLICT
#             )

#         # ✅ Create placeholder
#         placeholder_plan = DietRecommendation.objects.create(
#             user=patient,
#             for_week_starting=timezone.now().date(),
#             meals={},
#             original_ai_plan={},
#             status="generating",
#             reviewed_by=request.user
#         )

#         # 🚀 Trigger Celery
#         generate_ai_diet_task.delay(placeholder_plan.id)

#         serializer = DietRecommendationSerializer(placeholder_plan)
#         return Response(serializer.data, status=status.HTTP_201_CREATED)


#         if error:
#             return Response(
#                 {"error": error},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         serializer = DietRecommendationSerializer(new_plan)
#         return Response(serializer.data, status=status.HTTP_201_CREATED)

















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
    """
    Handles LISTING all lab reports for a specific patient (GET)
    and CREATING a new lab report for that patient (POST).
    """
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]
    serializer_class = LabReportSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['report_date']
    ordering_fields = ['report_date']

    def get_queryset(self):
        """
        This queryset is used for the LIST (GET) request.
        It ensures the nutritionist can only see reports for their assigned patients.
        """
        patient_id = self.kwargs['patient_id']
        # Check permission: Is the nutritionist assigned to this patient?
        if not PatientAssignment.objects.filter(nutritionist=self.request.user, patient_id=patient_id).exists():
            raise PermissionDenied("You are not assigned to this patient.")
        
        # Return all lab reports for that specific patient
        return LabReport.objects.filter(user_id=patient_id)

    def perform_create(self, serializer):
        """
        This method is called when CREATING a new lab report (POST).
        It automatically associates the new report with the patient from the URL.
        """
        patient_id = self.kwargs['patient_id']
        # Check permission before creating
        if not PatientAssignment.objects.filter(nutritionist=self.request.user, patient_id=patient_id).exists():
            raise PermissionDenied("You are not assigned to this patient.")
        
        # Fetch the patient user object
        try:
            patient_user = User.objects.get(pk=patient_id)
        except User.DoesNotExist:
            # This case is unlikely if the assignment check passes, but good for safety
            raise NotFound("Patient not found.")
            
        # Save the new lab report, injecting the user object
        serializer.save(user=patient_user)


class PatientLabReportDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Handles retrieving (GET), updating (PUT/PATCH), and deleting (DELETE)
    a SINGLE lab report by its ID.
    """
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]
    serializer_class = LabReportSerializer
    
    # The 'pk' in the URL will refer to the LabReport's ID.
    lookup_field = 'pk' 

    def get_queryset(self):
        """
        This queryset defines the pool of objects this view can access.
        We use it to enforce that the nutritionist can only interact with
        reports belonging to their assigned patients.
        """
        patient_id = self.kwargs['patient_id']
        if not PatientAssignment.objects.filter(nutritionist=self.request.user, patient_id=patient_id).exists():
            raise PermissionDenied("You are not assigned to this patient.")
        
        # The view will only be able to find reports belonging to this patient.
        return LabReport.objects.filter(user_id=patient_id)




###########--------------------TARGet------------------############

# ✅ For Nutritionist (Assigned Patients)
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
        # ✅ Check assignment
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
                "sedentary": 1.2,
                "light": 1.3,
                "lightly_active": 1.3,
                "moderate": 1.45,
                "active": 1.6,
                "very_active": 1.75
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
            protein_calories = protein_g * 4
            fats_calories = fats_g * 9
            carbs_calories = recommended_calories - (protein_calories + fats_calories)
            carbs_g = round(carbs_calories / 4) if carbs_calories > 0 else 0
            sugar_g = round((recommended_calories * 0.1) / 4)
            fiber_g = round((recommended_calories / 1000) * 14)

            base_water_ml = weight * 35
            activity_water_bonus = {
                "sedentary": 0,
                "light": 250,
                "lightly_active": 250,
                "moderate": 500,
                "active": 750,
                "very_active": 1000
            }
            recommended_water_ml = base_water_ml + activity_water_bonus.get(activity_level.lower(), 0)

            return Response({
                "bmr": round(bmr),
                "maintenance_calories": round(maintenance_calories),
                "recommended_calories": recommended_calories,
                "macronutrients": {
                    "protein_g": protein_g,
                    "carbs_g": carbs_g,
                    "fats_g": fats_g,
                    "sugar_g": sugar_g,
                    "fiber_g": fiber_g
                },
                "water": {
                    "recommended_ml": round(recommended_water_ml)
                },
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











class IsPatient(permissions.BasePermission):
    """
    Allows access only to authenticated users with the 'user' role.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'user'


# ==============================================================================
#           VIEWS FOR THE PATIENT (USER ROLE)
# ==============================================================================

# 🔹 NEW API VIEW FOR A PATIENT TO GET THEIR NUTRITIONIST'S DETAILS
class MyAssignedNutritionistView(APIView):
    """
    An endpoint for a logged-in patient (role='user') to retrieve
    the details of their assigned nutritionist.
    
    This is necessary for the patient to know the 'receiver' ID
    when sending a message.
    """
    permission_classes = [permissions.IsAuthenticated, IsPatient]

    def get(self, request, *args, **kwargs):
        # The logged-in user is the patient
        patient = request.user

        try:
            # Find the assignment where the current user is the patient
            assignment = PatientAssignment.objects.get(patient=patient)
            
            # Get the nutritionist from the assignment
            nutritionist = assignment.nutritionist
            
            # Use the existing UserSerializer1 to format the response
            serializer = UserSerializer1(nutritionist)
            
            # Return the nutritionist's data
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except PatientAssignment.DoesNotExist:
            # Handle the case where the patient has not been assigned a nutritionist yet
            return Response(
                {'error': 'You have not been assigned a nutritionist yet.'},
                status=status.HTTP_404_NOT_FOUND
            )




# ==============================================================================
# 🔹 NEW API VIEW: Restore (Unarchive) a Diet Plan
# ==============================================================================
class RestoreDietPlanView(generics.UpdateAPIView):
    """
    Handles restoring an archived diet plan by setting its 'is_deleted' flag to False.

    HTTP Method: PATCH
    URL: /api/nutritionist/diet-plans/<pk>/restore/
    Body: (Empty)
    """
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]
    serializer_class = DietRecommendationSerializer

    def get_queryset(self):
        """
        Security check: Ensures a nutritionist can only restore plans
        belonging to patients they are assigned to.
        """
        assigned_patient_ids = PatientAssignment.objects.filter(
            nutritionist=self.request.user
        ).values_list('patient_id', flat=True)
        
        # This view can only operate on plans that are currently archived.
        return DietRecommendation.objects.filter(
            user_id__in=assigned_patient_ids,
            is_deleted=True  # The key difference is here!
        )

    def patch(self, request, *args, **kwargs):
        """
        Handles the PATCH request to restore the plan.
        """
        # get_object() will find the plan using the pk from the URL.
        # It will correctly return a 404 Not Found if the plan isn't archived
        # or doesn't belong to an assigned patient, thanks to get_queryset.
        instance = self.get_object()
        
        # This is the reverse action:
        instance.is_deleted = False
        instance.save(update_fields=['is_deleted', 'updated_at'])
        
        return Response(
            {"message": "The diet plan has been successfully restored."},
            status=status.HTTP_200_OK
        )


class ArchiveDietPlanView(generics.UpdateAPIView):
    """
    Handles archiving a diet plan by setting its 'is_deleted' flag to True.
    This does NOT delete the record from the database. It only updates a field.

    HTTP Method: PATCH
    URL: /api/nutritionist/diet-plans/<pk>/archive/
    Body: (Empty)
    """
    permission_classes = [permissions.IsAuthenticated, IsNutritionist]
    serializer_class = DietRecommendationSerializer
    
    def get_queryset(self):
        """
        Security check: Ensures a nutritionist can only archive plans
        belonging to patients they are assigned to.
        """
        assigned_patient_ids = PatientAssignment.objects.filter(
            nutritionist=self.request.user
        ).values_list('patient_id', flat=True)
        
        # This view can only "see" and therefore update plans for assigned patients.
        # We also only need to deal with plans that are not yet archived.
        return DietRecommendation.objects.filter(
            user_id__in=assigned_patient_ids,
            is_deleted=False 
        )

    def patch(self, request, *args, **kwargs):
        """
        Handles the PATCH request to archive the plan.
        """
        # get_object() will find the plan using the primary key from the URL (pk)
        # and respect the queryset above. If the plan is already deleted or not
        # assigned to the nutritionist, it will correctly return a 404 Not Found.
        instance = self.get_object()
        
        # This is the ONLY action we perform:
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted', 'updated_at'])
        
        return Response(
            {"message": "The diet plan has been successfully archived."},
            status=status.HTTP_200_OK
        )