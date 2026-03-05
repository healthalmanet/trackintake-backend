from django.urls import path
from .views import (
    AllAssignedDietPlansListView,
    ApproveOrRejectDietView,
    AssignPatientAPIView,
    AssignedPatientsView,
    EditDietPlanView,
    GeneratePlanForPatientView,
    MyAssignedNutritionistView,
    NutritionistCreatePatientView,
    NutritionistPatientDietRecommendationsView,
    PatientDailySummaryView,
    PatientLabReportDetailView,
    PatientLabReportListCreateView,
    PatientLabReportsView, # Note: This might be redundant now with ListCreateView
    PatientMealLogView,
    PatientProfileDetailView,
    TargetNutrientsForPatientView,
    UpdateRetrainingFlagsView,
    UserListForNutritionistView,
    ArchiveDietPlanView,
    RestoreDietPlanView,
    # generate_plan_for_patient,
    # generate_plan_for_patient_view,
)

urlpatterns = [
    # ===================================================================
    # Nutritionist - General & Patient Management
    # ===================================================================
    path('nutritionist/users/', UserListForNutritionistView.as_view(), name='nutritionist-user-list'),
    path('nutritionist/assign-patient/', AssignPatientAPIView.as_view(), name='nutritionist-assign-patient'),
    path('nutritionist/patients/', AssignedPatientsView.as_view(), name='nutritionist-assigned-patients'),
    path('nutritionist/create-patient/', NutritionistCreatePatientView.as_view(), name='nutritionist-create-patient'),

    # ===================================================================
    # Nutritionist - Specific Patient Actions
    # ===================================================================
    path('nutritionist/patients/<int:patient_id>/profile/', PatientProfileDetailView.as_view(), name='nutritionist-patient-profile'),
    path('nutritionist/patients/<int:patient_id>/meals/', PatientMealLogView.as_view(), name='nutritionist-patient-meals'),
    path('nutritionist/patients/<int:patient_id>/daily-summary/', PatientDailySummaryView.as_view(), name='nutritionist-patient-summary'),
    path('nutritionist/patients/<int:patient_id>/target-nutrients/', TargetNutrientsForPatientView.as_view(), name='nutritionist-patient-targets'),
    path('nutritionist/patients/<int:patient_id>/generate-plan/', GeneratePlanForPatientView.as_view(), name='nutritionist-generate-patient-plan'),
    # path('nutritionist/patients/<int:patient_id>/generate-plan/', generate_plan_for_patient, name='generate-plan'),

    # ===================================================================
    # Nutritionist - Lab Report Management for a Patient
    # ===================================================================
    path('nutritionist/patients/<int:patient_id>/lab-reports/', PatientLabReportListCreateView.as_view(), name='patient-lab-report-list-create'),
    path('nutritionist/patients/<int:patient_id>/lab-reports/<int:pk>/', PatientLabReportDetailView.as_view(), name='patient-lab-report-detail'),
    path('nutritionist/patients/<int:patient_id>/lab-reports/', PatientLabReportsView.as_view()),

    # ===================================================================
    # Nutritionist - Diet Plan Management
    # ===================================================================
    # List all plans for all assigned patients
    path('nutritionist/diet-plans/', AllAssignedDietPlansListView.as_view(), name='nutritionist-all-diet-plans'),
    # List all plans for a specific patient
    path('nutritionist/patients/<int:patient_id>/diet-plans/', NutritionistPatientDietRecommendationsView.as_view(), name='nutritionist-patient-diet-plans'),

    # Actions on a specific diet plan
    path('nutritionist/diet-plans/<int:pk>/review/', ApproveOrRejectDietView.as_view(), name='review-diet-plan'),
    path('nutritionist/diet-plans/<int:pk>/feedback/', UpdateRetrainingFlagsView.as_view(), name='feedback-diet-plan'),
    path('nutritionist/diet-plans/<int:pk>/edit/', EditDietPlanView.as_view(), name='edit-diet-plan'),
    path('nutritionist/diet-plans/<int:pk>/archive/', ArchiveDietPlanView.as_view(), name='archive-diet-plan'),
    path('nutritionist/diet-plans/<int:pk>/restore/', RestoreDietPlanView.as_view(), name='restore-diet-plan'),

    # ===================================================================
    # Patient APIs
    # ===================================================================
    path('patient/my-nutritionist/', MyAssignedNutritionistView.as_view(), name='my-assigned-nutritionist'),
]