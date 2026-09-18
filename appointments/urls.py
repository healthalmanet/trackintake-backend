# from django.urls import path
# from .views import (
#     AvailableSlotsView,
#     BookAppointmentView,
#     MyAppointmentsView,
#     NutritionistAddAvailabilityView,
#     NutritionistMySlotsView,
#     NutritionistDeleteSlotView,
#     CancelAppointmentView,
#     DeleteSlotView,
#     MyInHouseNutritionistView,
#     ExpertNutritionistListView,
# )

# urlpatterns = [
#     # ----------------------
#     # Patient
#     # ----------------------
#     path(
#         "nutritionist/<int:nutritionist_id>/slots/",
#         AvailableSlotsView.as_view(),
#         name="available-slots",
#     ),
#     path(
#         "book/",
#         BookAppointmentView.as_view(),
#         name="book-appointment",
#     ),
#     path(
#         "my/",
#         MyAppointmentsView.as_view(),
#         name="my-appointments",
#     ),
#     path(
#         "me/in-house-nutritionist/",
#         MyInHouseNutritionistView.as_view(),
#         name="my-inhouse-nutritionist",
#     ),

#     # 🔥 EXPERT LIST (THIS WAS BROKEN)
#     path(
#         "expert-nutritionists/",
#         ExpertNutritionistListView.as_view(),
#         name="expert-nutritionists",
#     ),

#     # ----------------------
#     # Nutritionist
#     # ----------------------
#     path(
#         "nutritionist/add-availability/",
#         NutritionistAddAvailabilityView.as_view(),
#         name="add-availability",
#     ),
#     path(
#         "nutritionist/me/slots/",
#         NutritionistMySlotsView.as_view(),
#         name="nutritionist-my-slots",
#     ),
#     path(
#         "nutritionist/me/slots/<int:pk>/",
#         NutritionistDeleteSlotView.as_view(),
#         name="nutritionist-delete-slot",
#     ),
#     path(
#         "nutritionist/my-slots/",
#         NutritionistMySlotsView.as_view(),
#         name="nutritionist-slots",
#     ),
#     path(
#         "nutritionist/slots/<int:pk>/delete/",
#         DeleteSlotView.as_view(),
#         name="delete-slot",
#     ),

#     # ----------------------
#     # Appointment actions
#     # ----------------------
#     path(
#         "<int:pk>/cancel/",
#         CancelAppointmentView.as_view(),
#         name="cancel-appointment",
#     ),
# ]
from django.urls import path
from .views import (
    AvailableSlotsView,
    BookAppointmentView,
    MyAppointmentsView,
    AppointmentDetailView,
    AppointmentNotesUpdateView,
    PatientAppointmentHistoryView,
    NutritionistAddAvailabilityView,
    NutritionistMySlotsView,
    NutritionistDeleteSlotView,
    CancelAppointmentView,
    DeleteSlotView,
    MyInHouseNutritionistView,
    ExpertNutritionistListView,
    SubmitFeedbackView,
)

urlpatterns = [
    # Patient & General Appointment
    path("nutritionist/<int:nutritionist_id>/slots/", AvailableSlotsView.as_view()),
    path("book/", BookAppointmentView.as_view()),
    path("my/", MyAppointmentsView.as_view()),
    path("<int:pk>/", AppointmentDetailView.as_view(), name="appointment-detail"),
    path("<int:pk>/notes/", AppointmentNotesUpdateView.as_view(), name="appointment-notes"),
    path("patient-history/<int:patient_id>/", PatientAppointmentHistoryView.as_view(), name="patient-appointment-history"),

    # Nutritionist
    path("nutritionist/add-availability/", NutritionistAddAvailabilityView.as_view()),
    path("nutritionist/me/slots/", NutritionistMySlotsView.as_view()),
    path("nutritionist/me/slots/<int:pk>/", NutritionistDeleteSlotView.as_view()),
    path("nutritionist/my-slots/", NutritionistMySlotsView.as_view()),
    path("nutritionist/slots/<int:pk>/delete/", DeleteSlotView.as_view()),
    path("me/in-house-nutritionist/", MyInHouseNutritionistView.as_view()),
    path("expert-nutritionists/", ExpertNutritionistListView.as_view(), name="expert-nutritionists"),

    # Actions
    path("appointments/<int:pk>/cancel/", CancelAppointmentView.as_view()),
    path("<int:pk>/cancel/", CancelAppointmentView.as_view()),
    path("<int:appointment_id>/feedback/", SubmitFeedbackView.as_view(), name="submit-feedback"),
]
