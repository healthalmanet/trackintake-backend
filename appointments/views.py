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
    NutritionistPayoutSerializer,
)
from rest_framework import status
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from datetime import datetime, timedelta
from nutritionist.models import PatientAssignment
from user.models import User
from nutritionist.models import NutritionistProfile
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.utils.dateparse import parse_date
from django.utils.timezone import localdate
from appointments.zoom_service import create_zoom_meeting
from .email_utils import send_cancellation_emails, send_reschedule_emails


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
            
            # Fetch all distinct dates in the bulk payload
            dates = {item['date'] for item in serializer.validated_data}
            existing_slots = AvailabilitySlot.objects.filter(
                nutritionist=request.user,
                date__in=dates
            ).values('date', 'start_time', 'end_time')
            
            # Map existing slots by date for fast in-memory overlap checking
            existing_by_date = {}
            for s in existing_slots:
                existing_by_date.setdefault(s['date'], []).append((s['start_time'], s['end_time']))
            
            slots_to_create = []
            for item in serializer.validated_data:
                d = item['date']
                st = item['start_time']
                et = item['end_time']
                
                if st >= et:
                    errors.append(f"{d} {st}-{et}: Start time must be before end time.")
                    continue
                
                day_slots = existing_by_date.get(d, [])
                overlap = False
                for ex_st, ex_et in day_slots:
                    if st < ex_et and et > ex_st:
                        overlap = True
                        break
                
                if overlap:
                    errors.append(f"{d} {st}-{et}: Overlaps with an existing slot.")
                    continue
                
                day_slots.append((st, et))
                existing_by_date[d] = day_slots
                slots_to_create.append(
                    AvailabilitySlot(
                        nutritionist=request.user,
                        is_booked=False,
                        **item
                    )
                )
            
            if slots_to_create:
                with transaction.atomic():
                    created_slots = AvailabilitySlot.objects.bulk_create(slots_to_create)
            
            if not created_slots and errors:
                return Response(
                    {"detail": "Failed to create slots. All requested slots conflict with existing availability.", "errors": errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

            profile = getattr(request.user, "nutritionist_profile", None)
            return Response(
                {
                    "created_count": len(created_slots),
                    "slots": AvailabilitySlotSerializer(created_slots, many=True, context={"nutritionist_profile": profile}).data,
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
# CANCEL APPOINTMENT (Patient or Nutritionist)
# ─────────────────────────────────────────────
class CancelAppointmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        appointment = get_object_or_404(Appointment, id=pk)
        user = request.user

        # Permission check: must be patient, assigned nutritionist, or staff/admin
        if user != appointment.patient and user != appointment.nutritionist and not user.is_staff:
            return Response(
                {"detail": "You do not have permission to cancel this appointment."},
                status=status.HTTP_403_FORBIDDEN
            )

        if appointment.status == "CANCELLED":
            return Response(
                {"detail": "This appointment has already been cancelled."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get slot timing
        slot = appointment.slot
        slot_date = appointment.slot_date or (slot.date if slot else None)
        slot_start_time = appointment.slot_start_time or (slot.start_time if slot else None)

        if slot_date and slot_start_time:
            slot_start = timezone.make_aware(datetime.combine(slot_date, slot_start_time))
            if timezone.now() >= slot_start:
                return Response(
                    {"detail": "Cannot cancel an appointment that has already started or passed."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            time_diff = slot_start - timezone.now()
        else:
            time_diff = timedelta(days=1)

        reason = request.data.get("reason", "").strip()

        with transaction.atomic():
            # Restore slot availability so it can be booked again immediately
            if slot:
                slot.is_booked = False
                slot.save(update_fields=["is_booked"])

            if user == appointment.nutritionist:
                # ✅ Cancelled by Nutritionist: Patient is 100% eligible for refund if they paid
                appointment.cancelled_by = "NUTRITIONIST"
                if appointment.payment_status == "PAID" and appointment.fee_amount > 0:
                    appointment.payment_status = "PENDING_REFUND"
                    appointment.refund_amount = appointment.fee_amount
                    policy_msg = f"Notice: Cancelled by practitioner. Full refund of ₹{appointment.fee_amount} is marked as PENDING for the patient and will be processed by Admin."
                else:
                    appointment.payment_status = "NO_REFUND"
                    policy_msg = "Notice: Cancelled by practitioner. No upfront payment was required for this booking."
                appointment.payout_status = "CANCELLED"
            else:
                # ❌ Cancelled by Patient
                appointment.cancelled_by = "PATIENT"
                if time_diff < timedelta(hours=24):
                    # Within 24h: Policy -> No refund
                    appointment.payment_status = "NO_REFUND"
                    appointment.payout_status = "CANCELLED"
                    policy_msg = "Notice: Cancelled within 24 hours of scheduled appointment. As per platform policy, no refund applies."
                else:
                    # Cancelled >24h prior: Eligible for refund review by Admin
                    if appointment.payment_status == "PAID" and appointment.fee_amount > 0:
                        appointment.payment_status = "PENDING_REFUND"
                        appointment.refund_amount = appointment.fee_amount
                        policy_msg = f"Notice: Cancelled more than 24 hours prior. Refund of ₹{appointment.fee_amount} is marked as PENDING and will be processed by Admin."
                    else:
                        appointment.payment_status = "NO_REFUND"
                        policy_msg = "Notice: Cancelled more than 24 hours prior. No upfront payment was required for this booking."
                    appointment.payout_status = "CANCELLED"

            appointment.status = "CANCELLED"
            appointment.cancelled_at = timezone.now()
            appointment.cancellation_reason = reason
            appointment.save()

        # Send cancellation emails asynchronously to both patient and nutritionist
        try:
            send_cancellation_emails(appointment, appointment.cancelled_by, reason)
        except Exception as e:
            print(f"⚠️ Failed to send cancellation email: {e}")

        return Response({
            "detail": "Appointment cancelled successfully. The time slot is now available again.",
            "policy_notice": policy_msg,
            "appointment": AppointmentDetailSerializer(appointment, context={"request": request}).data,
        }, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────
# RESCHEDULE APPOINTMENT (Patient or Nutritionist)
# ─────────────────────────────────────────────
class RescheduleAppointmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        appointment = get_object_or_404(Appointment, id=pk)
        user = request.user

        if user != appointment.patient and user != appointment.nutritionist and not user.is_staff:
            return Response(
                {"detail": "You do not have permission to reschedule this appointment."},
                status=status.HTTP_403_FORBIDDEN
            )

        if appointment.status == "CANCELLED":
            return Response(
                {"detail": "Cannot reschedule a cancelled appointment. Please book a new slot."},
                status=status.HTTP_400_BAD_REQUEST
            )

        new_slot_id = request.data.get("new_slot_id") or request.data.get("slot_id")
        if not new_slot_id:
            return Response(
                {"detail": "Please select a new availability slot."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Current appointment timing
        slot = appointment.slot
        slot_date = appointment.slot_date or (slot.date if slot else None)
        slot_start_time = appointment.slot_start_time or (slot.start_time if slot else None)
        if slot_date and slot_start_time:
            current_start = timezone.make_aware(datetime.combine(slot_date, slot_start_time))
            if timezone.now() >= current_start:
                return Response(
                    {"detail": "Cannot reschedule an appointment that has already started or passed."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            time_diff = current_start - timezone.now()
        else:
            time_diff = timedelta(days=2)

        # Patient Rules:
        # 1. strictly before 24 hours
        # 2. limited to 2 times only
        is_patient = (user == appointment.patient)
        if is_patient:
            if time_diff < timedelta(hours=24):
                return Response(
                    {"detail": "Rescheduling is only available at least 24 hours before the appointment. Rescheduling is disabled within 24 hours of the appointment."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if appointment.reschedule_count >= 2:
                return Response(
                    {"detail": "You have already reached the maximum limit of 2 reschedules for this appointment."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Validate new slot
        try:
            new_slot = AvailabilitySlot.objects.get(id=new_slot_id)
        except AvailabilitySlot.DoesNotExist:
            return Response({"detail": "Selected slot does not exist."}, status=status.HTTP_404_NOT_FOUND)

        if new_slot.nutritionist_id != appointment.nutritionist_id:
            return Response({"detail": "You can only reschedule with the assigned nutritionist."}, status=status.HTTP_400_BAD_REQUEST)

        if new_slot.is_booked and new_slot.id != (appointment.slot_id or 0):
            return Response({"detail": "This slot is already booked. Please choose another future slot."}, status=status.HTTP_400_BAD_REQUEST)

        new_slot_start = timezone.make_aware(datetime.combine(new_slot.date, new_slot.start_time))
        if timezone.now() >= new_slot_start:
            return Response({"detail": "Selected slot is in the past. Please select a future slot."}, status=status.HTTP_400_BAD_REQUEST)

        # Check slot type compatibility
        if new_slot.slot_type != "BOTH" and new_slot.slot_type != appointment.appointment_type:
            type_label = "In-Clinic" if new_slot.slot_type == "IN_PERSON" else "Virtual"
            return Response(
                {"detail": f"This slot is reserved for {type_label} appointments and cannot be used for {appointment.appointment_type}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_slot_str = f"{slot_date} {slot_start_time.strftime('%I:%M %p')}" if slot_date and slot_start_time else "Previous Time"
        new_slot_str = f"{new_slot.date} {new_slot.start_time.strftime('%I:%M %p')}"

        with transaction.atomic():
            new_slot = AvailabilitySlot.objects.select_for_update().get(id=new_slot_id)
            if new_slot.is_booked and new_slot.id != (appointment.slot_id or 0):
                return Response({"detail": "This slot was just booked by someone else. Please choose another slot."}, status=status.HTTP_400_BAD_REQUEST)
            old_slot = appointment.slot
            if old_slot and old_slot.id != new_slot.id:
                old_slot.is_booked = False
                old_slot.save(update_fields=["is_booked"])

            new_slot.is_booked = True
            new_slot.save(update_fields=["is_booked"])

            # If virtual, refresh Zoom link for new datetime
            if appointment.appointment_type == "VIRTUAL":
                try:
                    duration = int(
                        (datetime.combine(new_slot.date, new_slot.end_time) -
                         datetime.combine(new_slot.date, new_slot.start_time)).total_seconds() / 60
                    )
                    patient_name = appointment.patient.full_name or appointment.patient.email
                    nutri_name = appointment.nutritionist.full_name or appointment.nutritionist.email
                    zoom_resp = create_zoom_meeting(
                        topic=f"Consultation: {patient_name} with {nutri_name}",
                        start_time_str=new_slot_start.isoformat(),
                        duration=duration
                    )
                    appointment.meeting_link = zoom_resp.get("join_url")
                except Exception as e:
                    print(f"⚠️ Zoom link refresh failed: {e}")

            appointment.slot = new_slot
            appointment.slot_date = new_slot.date
            appointment.slot_start_time = new_slot.start_time
            appointment.slot_end_time = new_slot.end_time
            if is_patient:
                appointment.reschedule_count += 1
            appointment.rescheduled_at = timezone.now()
            appointment.status = "CONFIRMED"
            appointment.save()

            # Refresh reminders for new time
            from .models import AppointmentReminder
            AppointmentReminder.objects.filter(appointment=appointment).delete()
            AppointmentReminder.objects.bulk_create([
                AppointmentReminder(
                    appointment=appointment,
                    remind_at=new_slot_start - timedelta(hours=24),
                    reminder_type="24H"
                ),
                AppointmentReminder(
                    appointment=appointment,
                    remind_at=new_slot_start - timedelta(hours=2),
                    reminder_type="2H"
                )
            ])

        # Send reschedule emails to both parties
        try:
            send_reschedule_emails(
                appointment=appointment,
                rescheduled_by_role="PATIENT" if is_patient else "NUTRITIONIST",
                old_slot_str=old_slot_str,
                new_slot_str=new_slot_str
            )
        except Exception as e:
            print(f"⚠️ Failed to send reschedule email: {e}")

        return Response({
            "detail": f"Appointment successfully rescheduled to {new_slot_str}.",
            "reschedules_used": appointment.reschedule_count,
            "reschedules_remaining": max(0, 2 - appointment.reschedule_count),
            "appointment": AppointmentDetailSerializer(appointment, context={"request": request}).data,
        }, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────
# NUTRITIONIST ONLINE EARNINGS & PAYOUTS
# ─────────────────────────────────────────────
class NutritionistPayoutsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role != "nutritionist" and not user.is_staff:
            return Response({"detail": "Only nutritionists can access earnings and payouts."}, status=status.HTTP_403_FORBIDDEN)

        # Auto-sync/backfill any appointments with missing financial calculations from profile
        profile = getattr(user, "nutritionist_profile", None)
        if profile:
            online_price = float(profile.online_price or 0.0)
            offline_price = float(profile.offline_price or 0.0)
            if online_price > 0 or offline_price > 0:
                uncalculated = Appointment.objects.filter(
                    nutritionist=user
                ).filter(
                    Q(fee_amount__lte=0) | Q(payout_amount__lte=0, appointment_type="VIRTUAL")
                )
                for appt in uncalculated:
                    price = online_price if appt.appointment_type == "VIRTUAL" else offline_price
                    if price > 0:
                        appt.fee_amount = price
                        if appt.appointment_type == "VIRTUAL" or profile.offline_payment_required:
                            if appt.payment_status in ["UNPAID", ""]:
                                appt.payment_status = "PAID"
                            if appt.payout_status in ["NOT_APPLICABLE", ""]:
                                appt.payout_status = "PENDING"
                            appt.payout_amount = price
                        appt.save(update_fields=["fee_amount", "payment_status", "payout_status", "payout_amount"])

        # All online booking appointments where revenue was handled by platform
        qs = Appointment.objects.filter(
            nutritionist=user
        ).filter(
            Q(appointment_type="VIRTUAL") | Q(fee_amount__gt=0)
        ).select_related(
            "patient", "slot"
        ).order_by("-created_at")

        search = request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(patient__full_name__icontains=search) |
                Q(patient__email__icontains=search) |
                Q(id__icontains=search)
            )

        payout_status = request.query_params.get("payout_status")
        if payout_status and payout_status != "ALL":
            qs = qs.filter(payout_status=payout_status)

        # Financial summary aggregation
        all_nutri_appts = Appointment.objects.filter(
            nutritionist=user
        ).filter(
            Q(appointment_type="VIRTUAL") | Q(fee_amount__gt=0)
        )

        total_earned = all_nutri_appts.filter(
            payout_status__in=["PAID", "PENDING"]
        ).aggregate(total=Sum("payout_amount"))["total"] or 0.0

        pending_payout = all_nutri_appts.filter(
            payout_status="PENDING"
        ).aggregate(total=Sum("payout_amount"))["total"] or 0.0

        completed_payout = all_nutri_appts.filter(
            payout_status="PAID"
        ).aggregate(total=Sum("payout_amount"))["total"] or 0.0

        total_bookings = all_nutri_appts.count()

        serializer = NutritionistPayoutSerializer(qs, many=True)
        return Response({
            "summary": {
                "total_earned": float(total_earned),
                "pending_payout": float(pending_payout),
                "completed_payout": float(completed_payout),
                "total_bookings": total_bookings,
            },
            "payouts": serializer.data,
        })


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

        profile = getattr(request.user, "nutritionist_profile", None)

        base_qs = AvailabilitySlot.objects.filter(nutritionist=request.user)

        # Global summary counts for the nutritionist (fast aggregated counts)
        total_available = base_qs.filter(is_booked=False).count()
        total_booked = base_qs.filter(is_booked=True).count()
        upcoming_count = base_qs.filter(
            Q(date__gt=today) | Q(date=today, end_time__gte=now_time)
        ).count()
        past_count = base_qs.filter(
            Q(date__lt=today) | Q(date=today, end_time__lt=now_time)
        ).count()

        qs = (
            base_qs
            .select_related(
                "nutritionist",
                "nutritionist__nutritionist_profile",
            )
            .prefetch_related(
                "appointments",
                "appointments__patient",
                "appointments__feedbacks",
                "appointments__feedbacks__given_by",
            )
        )

        # 🔍 Search by patient name or email
        if search:
            qs = qs.filter(
                Q(appointments__patient__full_name__icontains=search) |
                Q(appointments__patient__email__icontains=search)
            ).distinct()

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

        # ⏳ Filter by Upcoming / Past / All
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

        # Single DB query evaluation
        slot_list = list(qs)
        unbooked_list = [s for s in slot_list if not s.is_booked]
        booked_list = [s for s in slot_list if s.is_booked]

        serializer_context = {
            "request": request,
            "nutritionist_profile": profile,
        }

        return Response({
            "unbooked_slots": NutritionistSlotSerializer(
                unbooked_list, many=True, context=serializer_context
            ).data,
            "booked_slots": NutritionistSlotSerializer(
                booked_list, many=True, context=serializer_context
            ).data,
            "summary": {
                "total_available": total_available,
                "total_booked": total_booked,
                "upcoming_count": upcoming_count,
                "past_count": past_count,
                "total_count": total_available + total_booked,
            }
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