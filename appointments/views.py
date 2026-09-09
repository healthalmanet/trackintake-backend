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

from rest_framework.generics import ListAPIView, CreateAPIView, DestroyAPIView
from rest_framework.permissions import IsAuthenticated
from .models import AvailabilitySlot, Appointment
from .serializers import (
    AvailabilitySlotSerializer,
    AvailabilitySlotCreateSerializer,
    AppointmentCreateSerializer,
    AppointmentListSerializer,
    NutritionistSlotSerializer,AppointmentFeedbackSerializer,
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
        )
        data = [
            {"id": u.id, "name": u.full_name}
            for u in experts
        ]
        return Response(data)


# ─────────────────────────────────────────────
# IN-HOUSE NUTRITIONIST FOR LOGGED-IN PATIENT
# ─────────────────────────────────────────────
class MyInHouseNutritionistView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            assignment = PatientAssignment.objects.select_related(
                "nutritionist"
            ).get(patient=request.user)
        except PatientAssignment.DoesNotExist:
            return Response(
                {"detail": "No in-house nutritionist assigned"},
                status=404
            )

        return Response({
            "nutritionist_id": assignment.nutritionist.id,
            "nutritionist_name": assignment.nutritionist.full_name,
        })


# ─────────────────────────────────────────────
# AVAILABLE SLOTS FOR A NUTRITIONIST (Patient)
# ─────────────────────────────────────────────
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
        return Appointment.objects.filter(patient=self.request.user)


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