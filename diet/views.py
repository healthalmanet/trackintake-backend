from datetime import timedelta, date
from django.utils.timezone import now
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from ml_model.src.generator import generate_diet_plan
from diet.serializers import DietRecommendationSerializer
from userProfile.models import LabReport, UserProfile
from .models import DietRecommendation
import numpy as np
from django.core.paginator import Paginator
from django.utils.dateparse import parse_date   

from django.core.exceptions import ObjectDoesNotExist
from asgiref.sync import sync_to_async
import numpy as np
import traceback




class DietPlanView(APIView):
    """
    A unified endpoint for handling a user's 15-day diet plan.
    - GET: Fetch current active or pending plan.
    - POST: Generate a new plan (only if none is pending).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        today = now().date()

        try:
            # 1️⃣ Check for pending plan
            pending_plan = DietRecommendation.objects.filter(
                user=user, status='pending'
            ).order_by('-created_at').first()

            if pending_plan:
                return Response({
                    'status_code': 'PENDING_REVIEW',
                    'message': 'Your diet plan is currently under review.',
                    'plan_id': pending_plan.id
                }, status=status.HTTP_202_ACCEPTED)

            # 2️⃣ Check for valid 15-day approved plan
            active_plan = DietRecommendation.objects.filter(
                user=user, status='approved',
                for_week_starting__lte=today,
                for_week_starting__gte=today - timedelta(days=14)
            ).order_by('-for_week_starting').first()

            if active_plan:
                serializer = DietRecommendationSerializer(active_plan)
                return Response({
                    'status_code': 'ACTIVE_PLAN_FOUND',
                    'message': 'Displaying your active diet plan.',
                    'plan_data': serializer.data
                }, status=status.HTTP_200_OK)

            # 3️⃣ Nothing found
            return Response({
                'status_code': 'NO_PLAN_FOUND',
                'message': 'No active diet plan found. Please generate a new one.',
            }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            print(f"GET /diet-plan/ error for {user.email}: {e}")
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, *args, **kwargs):
        user = request.user
        print(f"[DEBUG] request.user: {request.user} | ID: {request.user.id} | Authenticated: {request.user.is_authenticated}")
        print(f"[DEBUG] UserProfile.exists: {UserProfile.objects.filter(user=request.user).exists()}")

        try:
            user_profile = UserProfile.objects.get(user=user)
            latest_lab_report = LabReport.objects.filter(user=user).order_by('-report_date').first()
        except UserProfile.DoesNotExist:
            return Response({'error': 'User profile not found. Please complete your profile.'}, status=status.HTTP_404_NOT_FOUND)

        # ⛔ Prevent spam: check if there's already a pending plan
        if DietRecommendation.objects.filter(user=user, status='pending').exists():
            return Response({
                'status_code': 'PENDING_REVIEW',
                'message': 'You already have a plan under review.',
            }, status=status.HTTP_409_CONFLICT)

        # 🔢 Build input vector snapshot (for audit/logging)
        NUMERICAL_COLS = [
            'Age', 'Weight (kg)', 'Height (cm)', 'BMI (auto-calculated)', 'Waist Circumference (cm)',
            'Fasting Blood Sugar (mg/dL)', 'HbA1c (%)', 'Postprandial Sugar (mg/dL)', 'LDL (mg/dL)',
            'HDL (mg/dL)', 'Triglycerides (mg/dL)', 'CRP (mg/L)', 'ESR (mm/hr)', 'Uric Acid (mg/dL)',
            'Creatinine (mg/dL)', 'Urea (mg/dL)', 'ALT (U/L)', 'AST (U/L)', 'Vitamin D3 (ng/mL)',
            'Vitamin B12 (pg/mL)', 'TSH (uIU/mL)'
        ]

        def calculate_age(dob):
            today = date.today()
            return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

        user_data_dict = {
            'Age': calculate_age(user_profile.date_of_birth),
            'Weight (kg)': user_profile.weight_kg,
            'Height (cm)': user_profile.height_cm,
            'BMI (auto-calculated)': user_profile.bmi,
            'Waist Circumference (cm)': getattr(latest_lab_report, 'waist_circumference_cm', 0),
            'Fasting Blood Sugar (mg/dL)': getattr(latest_lab_report, 'fasting_blood_sugar', 0),
            'HbA1c (%)': getattr(latest_lab_report, 'hba1c', 0),
            'Postprandial Sugar (mg/dL)': getattr(latest_lab_report, 'postprandial_sugar', 0),
            'LDL (mg/dL)': getattr(latest_lab_report, 'ldl_cholesterol', 0),
            'HDL (mg/dL)': getattr(latest_lab_report, 'hdl_cholesterol', 0),
            'Triglycerides (mg/dL)': getattr(latest_lab_report, 'triglycerides', 0),
            'CRP (mg/L)': getattr(latest_lab_report, 'crp', 0),
            'ESR (mm/hr)': getattr(latest_lab_report, 'esr', 0),
            'Uric Acid (mg/dL)': getattr(latest_lab_report, 'uric_acid', 0),
            'Creatinine (mg/dL)': getattr(latest_lab_report, 'creatinine', 0),
            'Urea (mg/dL)': getattr(latest_lab_report, 'urea', 0),
            'ALT (U/L)': getattr(latest_lab_report, 'alt', 0),
            'AST (U/L)': getattr(latest_lab_report, 'ast', 0),
            'Vitamin D3 (ng/mL)': getattr(latest_lab_report, 'vitamin_d3', 0),
            'Vitamin B12 (pg/mL)': getattr(latest_lab_report, 'vitamin_b12', 0),
            'TSH (uIU/mL)': getattr(latest_lab_report, 'tsh', 0),
        }

        user_vector_list = [
            float(user_data_dict.get(col, 0)) if user_data_dict.get(col, 0) is not None else 0.0
            for col in NUMERICAL_COLS
        ]

        try:
            print(f"Generating plan for user: {user.email}")
            plan_json = generate_diet_plan(user.id)  # 🔹 AI model call

            if isinstance(plan_json, dict) and "error" in plan_json:
                return Response({'error': plan_json['error']}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # ✅ Convert np.int64/float64 to native int/float for JSONField
            def convert_to_builtin_type(obj):
                if isinstance(obj, (np.integer, np.int64)): return int(obj)
                if isinstance(obj, (np.floating, np.float64)): return float(obj)
                if isinstance(obj, dict): return {k: convert_to_builtin_type(v) for k, v in obj.items()}
                if isinstance(obj, list): return [convert_to_builtin_type(i) for i in obj]
                return obj

            plan_json = convert_to_builtin_type(plan_json)

            new_recommendation = DietRecommendation.objects.create(
                user=user,
                for_week_starting=now().date(),
                meals=plan_json,
                original_ai_plan=plan_json,
                user_profile_snapshot=user_vector_list,
                status='pending'
            )
            return Response({
                'status_code': 'NEW_PLAN_GENERATED',
                'message': 'New diet plan generated successfully and is now under review.',
                'plan_id': new_recommendation.id,
            }, status=status.HTTP_201_CREATED)

        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import traceback; traceback.print_exc()
            return Response({'error': 'Internal error during diet generation.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




# class DietPlanView(APIView):
#     """
#     A unified endpoint for handling a user's 15-day diet plan.
#     - GET: Fetch current active or pending plan.
#     - POST: Generate a new plan (only if none is pending).
#     This view is now async to handle long-running tasks without blocking the server.
#     """
#     permission_classes = [permissions.IsAuthenticated]

#     # 👇 GET method is now async for consistency and to handle DB calls properly
#     async def get(self, request, *args, **kwargs):
#         user = request.user
#         today = now().date()

#         # The 'thread_sensitive=True' flag is best practice for Django ORM calls
#         @sync_to_async(thread_sensitive=True)
#         def get_plans():
#             # 1️⃣ Check for pending plan
#             pending_plan = DietRecommendation.objects.filter(
#                 user=user, status='pending'
#             ).order_by('-created_at').first()
#             if pending_plan:
#                 return 'pending', pending_plan

#             # 2️⃣ Check for valid 15-day approved plan
#             active_plan = DietRecommendation.objects.filter(
#                 user=user, status='approved',
#                 for_week_starting__lte=today,
#                 for_week_starting__gte=today - timedelta(days=14)
#             ).order_by('-for_week_starting').first()
#             if active_plan:
#                 return 'active', active_plan
            
#             return 'none', None

#         try:
#             plan_type, plan_object = await get_plans()

#             if plan_type == 'pending':
#                 return Response({
#                     'status_code': 'PENDING_REVIEW',
#                     'message': 'Your diet plan is currently under review.',
#                     'plan_id': plan_object.id
#                 }, status=status.HTTP_202_ACCEPTED)

#             if plan_type == 'active':
#                 serializer = DietRecommendationSerializer(plan_object)
#                 return Response({
#                     'status_code': 'ACTIVE_PLAN_FOUND',
#                     'message': 'Displaying your active diet plan.',
#                     'plan_data': serializer.data
#                 }, status=status.HTTP_200_OK)

#             # 3️⃣ Nothing found
#             return Response({
#                 'status_code': 'NO_PLAN_FOUND',
#                 'message': 'No active diet plan found. Please generate a new one.',
#             }, status=status.HTTP_404_NOT_FOUND)

#         except Exception as e:
#             print(f"GET /diet-plan/ error for {user.email}: {e}")
#             return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#     # 👇 POST method is now async. This is the main fix.
#     async def post(self, request, *args, **kwargs):
#         user = request.user
#         print(f"[DEBUG] request.user: {request.user} | ID: {request.user.id} | Authenticated: {request.user.is_authenticated}")

#         # 👇 We wrap all synchronous database calls in a helper function
#         @sync_to_async(thread_sensitive=True)
#         def get_required_data(user_obj):
#             try:
#                 user_profile = UserProfile.objects.get(user=user_obj)
#                 latest_lab_report = LabReport.objects.filter(user=user_obj).order_by('-report_date').first()
#                 has_pending_plan = DietRecommendation.objects.filter(user=user_obj, status='pending').exists()
#                 return user_profile, latest_lab_report, has_pending_plan, None
#             except UserProfile.DoesNotExist:
#                 return None, None, False, 'User profile not found. Please complete your profile.'
#             except Exception as e:
#                 return None, None, False, f"An unexpected database error occurred: {str(e)}"

#         # Await the results from the database thread
#         user_profile, latest_lab_report, has_pending_plan, error = await get_required_data(user)
        
#         if error:
#             status_code = status.HTTP_404_NOT_FOUND if "profile not found" in error else status.HTTP_500_INTERNAL_SERVER_ERROR
#             return Response({'error': error}, status=status_code)

#         # ⛔ Prevent spam: check if there's already a pending plan
#         if has_pending_plan:
#             return Response({
#                 'status_code': 'PENDING_REVIEW',
#                 'message': 'You already have a plan under review.',
#             }, status=status.HTTP_409_CONFLICT)
        
#         # This part is fast, pure-python logic. It does not need to be wrapped.
#         # 🔢 Build input vector snapshot
#         NUMERICAL_COLS = [
#             'Age', 'Weight (kg)', 'Height (cm)', 'BMI (auto-calculated)', 'Waist Circumference (cm)',
#             'Fasting Blood Sugar (mg/dL)', 'HbA1c (%)', 'Postprandial Sugar (mg/dL)', 'LDL (mg/dL)',
#             'HDL (mg/dL)', 'Triglycerides (mg/dL)', 'CRP (mg/L)', 'ESR (mm/hr)', 'Uric Acid (mg/dL)',
#             'Creatinine (mg/dL)', 'Urea (mg/dL)', 'ALT (U/L)', 'AST (U/L)', 'Vitamin D3 (ng/mL)',
#             'Vitamin B12 (pg/mL)', 'TSH (uIU/mL)'
#         ]

#         def calculate_age(dob):
#             today = date.today()
#             return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

#         user_data_dict = {
#             'Age': calculate_age(user_profile.date_of_birth), 'Weight (kg)': user_profile.weight_kg,
#             'Height (cm)': user_profile.height_cm, 'BMI (auto-calculated)': user_profile.bmi,
#             'Waist Circumference (cm)': getattr(latest_lab_report, 'waist_circumference_cm', 0),
#             'Fasting Blood Sugar (mg/dL)': getattr(latest_lab_report, 'fasting_blood_sugar', 0),
#             'HbA1c (%)': getattr(latest_lab_report, 'hba1c', 0),
#             'Postprandial Sugar (mg/dL)': getattr(latest_lab_report, 'postprandial_sugar', 0),
#             'LDL (mg/dL)': getattr(latest_lab_report, 'ldl_cholesterol', 0),
#             'HDL (mg/dL)': getattr(latest_lab_report, 'hdl_cholesterol', 0),
#             'Triglycerides (mg/dL)': getattr(latest_lab_report, 'triglycerides', 0),
#             'CRP (mg/L)': getattr(latest_lab_report, 'crp', 0),
#             'ESR (mm/hr)': getattr(latest_lab_report, 'esr', 0),
#             'Uric Acid (mg/dL)': getattr(latest_lab_report, 'uric_acid', 0),
#             'Creatinine (mg/dL)': getattr(latest_lab_report, 'creatinine', 0),
#             'Urea (mg/dL)': getattr(latest_lab_report, 'urea', 0), 'ALT (U/L)': getattr(latest_lab_report, 'alt', 0),
#             'AST (U/L)': getattr(latest_lab_report, 'ast', 0),
#             'Vitamin D3 (ng/mL)': getattr(latest_lab_report, 'vitamin_d3', 0),
#             'Vitamin B12 (pg/mL)': getattr(latest_lab_report, 'vitamin_b12', 0),
#             'TSH (uIU/mL)': getattr(latest_lab_report, 'tsh', 0),
#         }
#         user_vector_list = [float(user_data_dict.get(col, 0)) if user_data_dict.get(col, 0) is not None else 0.0 for col in NUMERICAL_COLS]

#         try:
#             print(f"Generating plan for user: {user.email}")
            
#             # 👇 THIS IS THE KEY CHANGE. We run the slow AI function in a thread.
#             # The web server is now free to handle other requests while this runs.
#             plan_json_from_ai = await sync_to_async(generate_diet_plan, thread_sensitive=True)(user.id)

#             if isinstance(plan_json_from_ai, dict) and "error" in plan_json_from_ai:
#                 return Response({'error': plan_json_from_ai['error']}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#             # This helper function is fine as it's fast and local
#             def convert_to_builtin_type(obj):
#                 if isinstance(obj, (np.integer, np.int64)): return int(obj)
#                 if isinstance(obj, (np.floating, np.float64)): return float(obj)
#                 if isinstance(obj, dict): return {k: convert_to_builtin_type(v) for k, v in obj.items()}
#                 if isinstance(obj, list): return [convert_to_builtin_type(i) for i in obj]
#                 return obj

#             plan_json = convert_to_builtin_type(plan_json_from_ai)

#             # 👇 Wrap the final database `create` call as well
#             @sync_to_async(thread_sensitive=True)
#             def create_new_recommendation():
#                 return DietRecommendation.objects.create(
#                     user=user, for_week_starting=now().date(), meals=plan_json,
#                     original_ai_plan=plan_json, user_profile_snapshot=user_vector_list,
#                     status='pending'
#                 )
            
#             new_recommendation = await create_new_recommendation()

#             return Response({
#                 'status_code': 'NEW_PLAN_GENERATED',
#                 'message': 'New diet plan generated successfully and is now under review.',
#                 'plan_id': new_recommendation.id,
#             }, status=status.HTTP_201_CREATED)

#         except ValueError as e:
#             return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
#         except Exception as e:
#             traceback.print_exc()
#             return Response({'error': 'Internal error during diet generation.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)






class PreviousDietPlansView(APIView):
    """
    GET /diet-plan/history/
    🔹 Filters:
        - status=approved|rejected
        - start_date=YYYY-MM-DD
        - end_date=YYYY-MM-DD
        - limit=<int> (default: 10)
        - offset=<int> (default: 0)
    🔹 Shows all previous plans (except pending) for logged-in user.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        status_filter = request.query_params.get('status')
        start_date = parse_date(request.query_params.get('start_date', ''))
        end_date = parse_date(request.query_params.get('end_date', ''))
        limit = int(request.query_params.get('limit', 10))
        offset = int(request.query_params.get('offset', 0))

        try:
            queryset = DietRecommendation.objects.filter(user=user)

            if status_filter in ['approved', 'rejected']:
                queryset = queryset.filter(status=status_filter)

            if start_date:
                queryset = queryset.filter(for_week_starting__gte=start_date)

            if end_date:
                queryset = queryset.filter(for_week_starting__lte=end_date)

            queryset = queryset.exclude(status='pending').order_by('-for_week_starting')

            total = queryset.count()
            paginator = Paginator(queryset, limit)
            page_number = offset // limit + 1
            page = paginator.get_page(page_number)

            serializer = DietRecommendationSerializer(page.object_list, many=True)

            return Response({
                'status_code': 'HISTORY_FOUND',
                'total': total,
                'limit': limit,
                'offset': offset,
                'plans_returned': len(page.object_list),
                'plans': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"[ERROR] GET /diet-plan/history/ for {user.email}: {e}")
            return Response({'error': 'Error while fetching previous plans.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
