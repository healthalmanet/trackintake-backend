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
    RescheduleAppointmentView,
    NutritionistPayoutsView,
    DeleteSlotView,
    MyInHouseNutritionistView,
    ExpertNutritionistListView,
    SubmitFeedbackView,
    MarkAppointmentPaidView,
    SetAppointmentPriceView,
    DeclineAppointmentCaseView,
    ConfirmQuotedPaymentView,
    AppointmentNotificationListView,
    MarkAppointmentNotificationReadView,
)

urlpatterns = [
    # In-App Notifications
    path("notifications/", AppointmentNotificationListView.as_view(), name="appointment-notifications"),
    path("notifications/mark-read/", MarkAppointmentNotificationReadView.as_view(), name="appointment-notifications-mark-read"),

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
    path("nutritionist/payouts/", NutritionistPayoutsView.as_view(), name="nutritionist-payouts"),
    path("me/in-house-nutritionist/", MyInHouseNutritionistView.as_view()),
    path("expert-nutritionists/", ExpertNutritionistListView.as_view(), name="expert-nutritionists"),

    # Actions: Cancel, Reschedule & Mark Paid
    path("appointments/<int:pk>/cancel/", CancelAppointmentView.as_view(), name="cancel-appointment"),
    path("<int:pk>/cancel/", CancelAppointmentView.as_view()),
    path("appointments/<int:pk>/reschedule/", RescheduleAppointmentView.as_view(), name="reschedule-appointment"),
    path("<int:pk>/reschedule/", RescheduleAppointmentView.as_view()),
    path("<int:pk>/mark-paid/", MarkAppointmentPaidView.as_view(), name="mark-appointment-paid"),
    path("appointments/<int:pk>/mark-paid/", MarkAppointmentPaidView.as_view()),
    path("<int:appointment_id>/feedback/", SubmitFeedbackView.as_view(), name="submit-feedback"),

    # Two-step variable case appointments: Quoting, Declining & Quoted Payment Confirmation
    path("appointments/<int:pk>/set-price/", SetAppointmentPriceView.as_view(), name="set-appointment-price"),
    path("<int:pk>/set-price/", SetAppointmentPriceView.as_view()),
    path("appointments/<int:pk>/decline-case/", DeclineAppointmentCaseView.as_view(), name="decline-appointment-case"),
    path("<int:pk>/decline-case/", DeclineAppointmentCaseView.as_view()),
    path("appointments/<int:pk>/confirm-payment/", ConfirmQuotedPaymentView.as_view(), name="confirm-quoted-payment"),
    path("<int:pk>/confirm-payment/", ConfirmQuotedPaymentView.as_view()),
]
