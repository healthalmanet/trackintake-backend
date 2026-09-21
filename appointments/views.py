# from rest_framework.generics import ListAPIView, CreateAPIView,DestroyAPIView
# from rest_framework.permissions import IsAuthenticated
# from .models import AvailabilitySlot, Appointment
# from .serializers import (
#     AvailabilitySlotSerializer,
#     AvailabilitySlotCreateSerializer,
#     AppointmentCreateSerializer,
#     AppointmentListSerializer,
#     NutritionistSlotSerializer
# )
# from rest_framework import status
# from django.shortcuts import get_object_or_404
# from .models import Appointment
# from rest_framework.response import Response
# from rest_framework.views import APIView
# from django.utils import timezone
# from datetime import datetime

# from rest_framework.views import APIView
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.response import Response
# from nutritionist.models import PatientAssignment

# from user.models import User
# from nutritionist.models import NutritionistProfile
# from rest_framework.views import APIView
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.response import Response
# from subscriptions.services import consume_consultation
# from django.db import transaction

# class ExpertNutritionistListView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         experts = User.objects.filter(
#             role="nutritionist",
#             nutritionist_profile__nutritionist_type=NutritionistProfile.NutritionistType.EXPERT
#         )

#         data = [
#             {"id": u.id, "name": u.full_name}
#             for u in experts
#         ]
#         return Response(data)


# class MyInHouseNutritionistView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         try:
#             assignment = PatientAssignment.objects.select_related(
#                 "nutritionist"
#             ).get(patient=request.user)
#         except PatientAssignment.DoesNotExist:
#             return Response(
#                 {"detail": "No in-house nutritionist assigned"},
#                 status=404
#             )

#         return Response({
#             "nutritionist_id": assignment.nutritionist.id,
#             "nutritionist_name": assignment.nutritionist.full_name,
#         })

# # Patient
# class AvailableSlotsView(ListAPIView):
#     serializer_class = AvailabilitySlotSerializer

#     def get_queryset(self):
#         nutritionist_id = self.kwargs['nutritionist_id']
#         date = self.request.query_params.get('date')
#         return AvailabilitySlot.objects.filter(
#             nutritionist_id=nutritionist_id,
#             date=date,
#             is_booked=False
#         )


# class BookAppointmentView(CreateAPIView):
#     serializer_class = AppointmentCreateSerializer
#     permission_classes = [IsAuthenticated]

# @transaction.atomic
# def perform_create(self, serializer):
#     slot = serializer.validated_data["slot"]
#     consult_type = serializer.validated_data["consult_type"]
#     nutritionist = slot.nutritionist

#     # 🔒 Enforce correct quota
#     consume_consultation(
#         user=self.request.user,
#         consult_type=consult_type
#     )

#     # 🔐 Slot lock
#     slot = AvailabilitySlot.objects.select_for_update().get(id=slot.id)
#     if slot.is_booked:
#         raise ValueError("Slot already booked")

#     appointment = serializer.save(
#         patient=self.request.user,
#         nutritionist=nutritionist
#     )

#     slot.is_booked = True
#     slot.save(update_fields=["is_booked"])



# class MyAppointmentsView(ListAPIView):
#     serializer_class = AppointmentListSerializer
#     permission_classes = [IsAuthenticated]

#     def get_queryset(self):
#         return Appointment.objects.filter(patient=self.request.user)


# # Nutritionist
# class NutritionistAddAvailabilityView(CreateAPIView):
#     serializer_class = AvailabilitySlotCreateSerializer
#     permission_classes = [IsAuthenticated]

#     def perform_create(self, serializer):
#         serializer.save(
#             nutritionist=self.request.user,
#             is_booked=False
#         )


# # # Nutritionist: view own slots
# # class NutritionistMySlotsView(ListAPIView):
# #     serializer_class = AvailabilitySlotSerializer
# #     permission_classes = [IsAuthenticated]

# #     def get_queryset(self):
# #         date = self.request.query_params.get("date")
# #         qs = AvailabilitySlot.objects.filter(
# #             nutritionist=self.request.user
# #         )
# #         if date:
# #             qs = qs.filter(date=date)
# #         return qs


# # Nutritionist: delete own slot
# class NutritionistDeleteSlotView(DestroyAPIView):
#     permission_classes = [IsAuthenticated]

#     def get_queryset(self):
#         return AvailabilitySlot.objects.filter(
#             nutritionist=self.request.user,
#             is_booked=False  # prevent deleting booked slots
#         )



    
# class CancelAppointmentView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request, pk):
#         appointment = get_object_or_404(
#             Appointment,
#             id=pk,
#             patient=request.user
#         )

#         slot = appointment.slot

#         slot_start = datetime.combine(
#             slot.date,
#             slot.start_time,
#             tzinfo=timezone.get_current_timezone()
#         )

#         if timezone.now() >= slot_start:
#             return Response(
#                 {"detail": "Cannot cancel after appointment has started"},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         appointment.delete()
#         slot.is_booked = False
#         slot.save()

#         return Response({"detail": "Appointment cancelled"})

# class DeleteSlotView(APIView):
#     permission_classes = [IsAuthenticated]

#     def delete(self, request, pk):
#         slot = get_object_or_404(
#             AvailabilitySlot,
#             id=pk,
#             nutritionist=request.user
#         )

#         if slot.is_booked:
#             return Response(
#                 {"detail": "Cannot delete a booked slot"},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         slot.delete()
#         return Response({"detail": "Slot deleted"})


# from django.utils.timezone import localdate
# from django.db.models import Q

# # class NutritionistMySlotsView(ListAPIView):
# #     permission_classes = [IsAuthenticated]
# #     serializer_class = NutritionistSlotSerializer

# #     def get_queryset(self):
# #         today = localdate()

# #         return AvailabilitySlot.objects.filter(
# #             nutritionist=self.request.user
# #         ).filter(
# #             Q(date__gte=today) | Q(is_booked=True)
# #         ).order_by("-date", "-start_time")
# from django.db.models import Q
# from django.utils.dateparse import parse_date

# class NutritionistMySlotsView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         search = request.query_params.get("search")
#         date = request.query_params.get("date")
#         status = request.query_params.get("status")  # booked / unbooked

#         qs = (
#             AvailabilitySlot.objects
#             .filter(nutritionist=request.user)
#             .select_related(
#                 "appointment",
#                 "appointment__patient",
#             )
#         )

#         # 🔍 Search by patient name or email
#         if search:
#             qs = qs.filter(
#                 Q(appointment__patient__full_name__icontains=search) |
#                 Q(appointment__patient__email__icontains=search)
#             )

#         # 📅 Filter by date
#         if date:
#             parsed_date = parse_date(date)
#             if parsed_date:
#                 qs = qs.filter(date=parsed_date)

#         # 📌 Filter by status
#         if status == "booked":
#             qs = qs.filter(is_booked=True)
#         elif status == "unbooked":
#             qs = qs.filter(is_booked=False)

#         qs = qs.order_by("-date", "-start_time")

#         return Response({
#             "unbooked_slots": NutritionistSlotSerializer(
#                 qs.filter(is_booked=False), many=True
#             ).data,
#             "booked_slots": NutritionistSlotSerializer(
#                 qs.filter(is_booked=True), many=True
#             ).data,
#         })

from rest_framework.generics import ListAPIView, CreateAPIView, DestroyAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from .models import AvailabilitySlot, Appointment
from .serializers import (
    AvailabilitySlotSerializer,
    AvailabilitySlotCreateSerializer,
    AppointmentCreateSerializer,
    AppointmentListSerializer,
    AppointmentDetailSerializer,
    AppointmentNotesUpdateSerializer,
    NutritionistSlotSerializer,
    AppointmentFeedbackSerializer,
)
from rest_framework import status
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from datetime import datetime
from nutritionist.models import PatientAssignment
from user.models import User
from nutritionist.models import NutritionistProfile
from django.db import transaction
from django.db.models import Q
from django.utils.dateparse import parse_date
from django.utils.timezone import localdate


# ─────────────────────────────────────────────
# EXPERT NUTRITIONIST LIST
# ─────────────────────────────────────────────
class ExpertNutritionistListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        experts = User.objects.filter(
            role="nutritionist",
            nutritionist_profile__nutritionist_type=NutritionistProfile.NutritionistType.EXPERT
        ).select_related("nutritionist_profile")
        
        from user.serializers import sanitize_json_string_list

        data = []
        for u in experts:
            profile = getattr(u, "nutritionist_profile", None)
            data.append({
                "id": u.id,
                "name": u.full_name or u.username,
                "email": u.email,
                "professional_title": profile.professional_title if profile else "Clinical Nutritionist",
                "qualification": profile.qualification if profile else "",
                "years_of_experience": profile.years_of_experience if profile else 0,
                "specializations": sanitize_json_string_list(profile.specializations) if profile else [],
                "languages_spoken": sanitize_json_string_list(profile.languages_spoken) if profile else [],
                "is_online_available": profile.is_online_available if profile else True,
                "is_offline_available": profile.is_offline_available if profile else False,
                "online_price": float(profile.online_price) if profile and profile.online_price is not None else 0.0,
                "offline_price": float(profile.offline_price) if profile and profile.offline_price is not None else 0.0,
                "offline_payment_required": profile.offline_payment_required if profile else True,
                "offline_location": profile.offline_location if profile else "",
            })
        return Response(data)


# ─────────────────────────────────────────────
# IN-HOUSE NUTRITIONIST FOR LOGGED-IN PATIENT
# ─────────────────────────────────────────────
class MyInHouseNutritionistView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            assignment = PatientAssignment.objects.select_related(
                "nutritionist", "nutritionist__nutritionist_profile"
            ).get(patient=request.user)
        except PatientAssignment.DoesNotExist:
            return Response(
                {"detail": "No in-house nutritionist assigned"},
                status=404
            )

        nutri = assignment.nutritionist
        profile = getattr(nutri, "nutritionist_profile", None)
        from user.serializers import sanitize_json_string_list

        return Response({
            "nutritionist_id": nutri.id,
            "nutritionist_name": nutri.full_name or nutri.username,
            "nutritionist_email": nutri.email,
            "professional_title": profile.professional_title if profile else "Clinical Nutritionist",
            "qualification": profile.qualification if profile else "",
            "specializations": sanitize_json_string_list(profile.specializations) if profile else [],
            "languages_spoken": sanitize_json_string_list(profile.languages_spoken) if profile else [],
            "is_online_available": profile.is_online_available if profile else True,
            "is_offline_available": profile.is_offline_available if profile else False,
            "online_price": float(profile.online_price) if profile and profile.online_price is not None else 0.0,
            "offline_price": float(profile.offline_price) if profile and profile.offline_price is not None else 0.0,
            "offline_payment_required": profile.offline_payment_required if profile else True,
            "offline_location": profile.offline_location if profile else "",
        })


# ─────────────────────────────────────────────
# AVAILABLE SLOTS FOR A NUTRITIONIST (Patient)
# ─────────────────────────────────────────────
class AvailableSlotsView(ListAPIView):
    serializer_class = AvailabilitySlotSerializer

    def get_queryset(self):
        nutritionist_id = self.kwargs['nutritionist_id']
        date = self.request.query_params.get('date')
        appointment_type = self.request.query_params.get('appointment_type')

        qs = AvailabilitySlot.objects.filter(
            nutritionist_id=nutritionist_id,
            date=date,
            is_booked=False
        )

        if appointment_type:
            qs = qs.filter(
                Q(slot_type=appointment_type) | Q(slot_type="BOTH")
            )

        return qs


# ─────────────────────────────────────────────
# BOOK APPOINTMENT (FIXED)
# ─────────────────────────────────────────────
class BookAppointmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AppointmentCreateSerializer(
            data=request.data,
            context={"request": request}
        )
        if serializer.is_valid(raise_exception=True):
            appointment = serializer.save()
            return Response(
                AppointmentListSerializer(appointment).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
# MY APPOINTMENTS (Patient)
# ─────────────────────────────────────────────
class MyAppointmentsView(ListAPIView):
    serializer_class = AppointmentListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Appointment.objects.filter(
            patient=self.request.user
        ).select_related(
            "nutritionist",
            "nutritionist__nutritionist_profile",
            "slot"
        ).prefetch_related(
            "feedbacks",
            "feedbacks__given_by"
        )

        status_param = self.request.query_params.get("status")
        type_param = self.request.query_params.get("appointment_type")
        time_horizon = self.request.query_params.get("time_horizon")
        date_param = self.request.query_params.get("date")
        search = self.request.query_params.get("search")

        if status_param and status_param != "ALL":
            qs = qs.filter(status=status_param)

        if type_param and type_param != "ALL":
            qs = qs.filter(appointment_type=type_param)

        if date_param:
            parsed = parse_date(date_param)
            if parsed:
                qs = qs.filter(slot__date=parsed)

        if search:
            qs = qs.filter(
                Q(nutritionist__full_name__icontains=search) |
                Q(nutritionist__email__icontains=search)
            )

        today = localdate()
        now_time = timezone.localtime().time()

        if time_horizon == "upcoming":
            qs = qs.filter(
                Q(slot__date__gt=today) |
                Q(slot__date=today, slot__end_time__gte=now_time)
            ).order_by("slot__date", "slot__start_time")
        elif time_horizon == "past":
            qs = qs.filter(
                Q(slot__date__lt=today) |
                Q(slot__date=today, slot__end_time__lt=now_time)
            ).order_by("-slot__date", "-slot__start_time")
        else:
            qs = qs.order_by("-created_at")

        return qs


# ─────────────────────────────────────────────
# NUTRITIONIST: ADD AVAILABILITY SLOT(S)
# ─────────────────────────────────────────────
class NutritionistAddAvailabilityView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        # Support both single slot and list of slots
        is_bulk = isinstance(data, list)
        
        if is_bulk:
            serializer = AvailabilitySlotCreateSerializer(data=data, many=True)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            created_slots = []
            errors = []
            
            with transaction.atomic():
                for item in serializer.validated_data:
                    slot = AvailabilitySlot(
                        nutritionist=request.user,
                        is_booked=False,
                        **item
                    )
                    try:
                        slot.full_clean()
                        slot.save()
                        created_slots.append(slot)
                    except Exception as e:
                        errors.append(f"{item.get('start_time')}-{item.get('end_time')}: {str(e)}")
            
            if not created_slots and errors:
                return Response(
                    {"detail": "Failed to create slots.", "errors": errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response(
                {
                    "created_count": len(created_slots),
                    "slots": AvailabilitySlotSerializer(created_slots, many=True).data,
                    "errors": errors if errors else None,
                },
                status=status.HTTP_201_CREATED
            )
        else:
            serializer = AvailabilitySlotCreateSerializer(data=data)
            if serializer.is_valid():
                try:
                    slot = serializer.save(
                        nutritionist=request.user,
                        is_booked=False
                    )
                    return Response(
                        AvailabilitySlotSerializer(slot).data,
                        status=status.HTTP_201_CREATED
                    )
                except Exception as e:
                    return Response(
                        {"detail": str(e)},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
# NUTRITIONIST: DELETE OWN SLOT (generic)
# ─────────────────────────────────────────────
class NutritionistDeleteSlotView(DestroyAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AvailabilitySlot.objects.filter(
            nutritionist=self.request.user,
            is_booked=False  # prevent deleting booked slots
        )


# ─────────────────────────────────────────────
# CANCEL APPOINTMENT (Patient)
# ─────────────────────────────────────────────
class CancelAppointmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        appointment = get_object_or_404(
            Appointment,
            id=pk,
            patient=request.user
        )

        slot = appointment.slot

        slot_start = datetime.combine(
            slot.date,
            slot.start_time,
            tzinfo=timezone.get_current_timezone()
        )

        if timezone.now() >= slot_start:
            return Response(
                {"detail": "Cannot cancel after appointment has started"},
                status=status.HTTP_400_BAD_REQUEST
            )

        appointment.delete()
        slot.is_booked = False
        slot.save()

        return Response({"detail": "Appointment cancelled"})


# ─────────────────────────────────────────────
# DELETE SLOT (Nutritionist)
# ─────────────────────────────────────────────
class DeleteSlotView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        slot = get_object_or_404(
            AvailabilitySlot,
            id=pk,
            nutritionist=request.user
        )

        if slot.is_booked:
            return Response(
                {"detail": "Cannot delete a booked slot"},
                status=status.HTTP_400_BAD_REQUEST
            )

        slot.delete()
        return Response({"detail": "Slot deleted"})


# ─────────────────────────────────────────────
# NUTRITIONIST: MY SLOTS (with filters)
# ─────────────────────────────────────────────
class NutritionistMySlotsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        search = request.query_params.get("search")
        date = request.query_params.get("date")
        slot_status = request.query_params.get("status")  # booked / unbooked
        slot_type = request.query_params.get("slot_type")  # VIRTUAL / IN_PERSON / BOTH
        time_horizon = request.query_params.get("time_horizon") or request.query_params.get("period")  # upcoming / past / all

        today = localdate()
        now_time = timezone.localtime().time()

        qs = (
            AvailabilitySlot.objects
            .filter(nutritionist=request.user)
            .select_related(
                "appointment",
                "appointment__patient",
            )
        )

        # 🔍 Search by patient name or email
        if search:
            qs = qs.filter(
                Q(appointment__patient__full_name__icontains=search) |
                Q(appointment__patient__email__icontains=search)
            )

        # 📅 Filter by date
        if date:
            parsed_date = parse_date(date)
            if parsed_date:
                qs = qs.filter(date=parsed_date)

        # 🏷️ Filter by slot type
        if slot_type:
            qs = qs.filter(slot_type=slot_type)

        # 📌 Filter by status
        if slot_status == "booked":
            qs = qs.filter(is_booked=True)
        elif slot_status == "unbooked":
            qs = qs.filter(is_booked=False)

        # ⏳ Filter by Upcoming / Past
        if time_horizon == "upcoming":
            qs = qs.filter(
                Q(date__gt=today) |
                Q(date=today, end_time__gte=now_time)
            ).order_by("date", "start_time")
        elif time_horizon == "past":
            qs = qs.filter(
                Q(date__lt=today) |
                Q(date=today, end_time__lt=now_time)
            ).order_by("-date", "-start_time")
        else:
            qs = qs.order_by("date", "start_time")

        return Response({
            "unbooked_slots": NutritionistSlotSerializer(
                qs.filter(is_booked=False), many=True
            ).data,
            "booked_slots": NutritionistSlotSerializer(
                qs.filter(is_booked=True), many=True
            ).data,
        })
    
class SubmitFeedbackView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, appointment_id):
        appointment = get_object_or_404(Appointment, id=appointment_id)

        serializer = AppointmentFeedbackSerializer(
            data={
                **request.data,
                "given_by": request.user.id,
                "role": "PATIENT",
                "appointment": appointment.id
            },
            context={"request": request}
        )

        if serializer.is_valid():
            serializer.save(appointment=appointment)
            return Response({"message": "Feedback submitted"}, status=201)

        return Response(serializer.errors, status=400)


# ─────────────────────────────────────────────
# APPOINTMENT DETAIL (Patient & Nutritionist)
# ─────────────────────────────────────────────
class AppointmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        appointment = get_object_or_404(
            Appointment.objects.select_related(
                "patient",
                "nutritionist",
                "nutritionist__nutritionist_profile",
                "slot",
            ).prefetch_related(
                "feedbacks",
                "feedbacks__given_by",
            ),
            id=pk
        )

        # Allow access only to the patient, nutritionist, or staff
        if (
            appointment.patient != request.user
            and appointment.nutritionist != request.user
            and not request.user.is_staff
        ):
            return Response(
                {"detail": "You do not have permission to view this appointment."},
                status=status.HTTP_403_FORBIDDEN
            )

        return Response(AppointmentDetailSerializer(appointment).data)


# ─────────────────────────────────────────────
# APPOINTMENT NOTES & INSTRUCTIONS UPDATE (Nutritionist)
# ─────────────────────────────────────────────
class AppointmentNotesUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        appointment = get_object_or_404(Appointment, id=pk)

        # Allow only the assigned nutritionist or staff to update clinical notes
        if appointment.nutritionist != request.user and not request.user.is_staff:
            return Response(
                {"detail": "Only the assigned nutritionist can update appointment notes."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = AppointmentNotesUpdateSerializer(
            appointment,
            data=request.data,
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                AppointmentDetailSerializer(appointment).data,
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
# PATIENT APPOINTMENT HISTORY (For Nutritionist / Admin)
# ─────────────────────────────────────────────
class PatientAppointmentHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, patient_id):
        patient = get_object_or_404(User, id=patient_id)

        # Nutritionists and Staff can view appointments of the patient
        # Patient can also view their own
        if (
            request.user.role != "nutritionist"
            and not request.user.is_staff
            and request.user.id != patient.id
        ):
            return Response(
                {"detail": "Permission denied to view this patient's appointments."},
                status=status.HTTP_403_FORBIDDEN
            )

        appointments = Appointment.objects.filter(
            patient=patient
        ).select_related(
            "nutritionist",
            "nutritionist__nutritionist_profile",
            "slot"
        ).prefetch_related(
            "feedbacks",
            "feedbacks__given_by"
        ).order_by("-slot__date", "-slot__start_time")

        return Response(AppointmentListSerializer(appointments, many=True).data)