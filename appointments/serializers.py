import uuid
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from django.core.exceptions import ObjectDoesNotExist
from .models import Appointment, AvailabilitySlot
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import datetime, timedelta
from .models import AppointmentReminder
from nutritionist.models import PatientAssignment
from subscriptions.services import consume_consultation

User = get_user_model()

# ---------- Slots ----------
class AvailabilitySlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailabilitySlot
        fields = ['id', 'date', 'start_time', 'end_time']


class AvailabilitySlotCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailabilitySlot
        fields = ['date', 'start_time', 'end_time']


# ---------- Appointment ----------
# class AppointmentCreateSerializer(serializers.Serializer):
#     slot_id = serializers.IntegerField()
#     appointment_type = serializers.ChoiceField(
#         choices=['IN_PERSON', 'VIRTUAL']
#     )

#     def validate(self, data):
#         try:
#             slot = AvailabilitySlot.objects.get(id=data['slot_id'])
#         except AvailabilitySlot.DoesNotExist:
#             raise serializers.ValidationError("Invalid slot")

#         if slot.is_booked:
#             raise serializers.ValidationError("Slot already booked")

#         if data['appointment_type'] == 'VIRTUAL':
#             try:
#                 profile = slot.nutritionist.nutritionist_profile
#             except ObjectDoesNotExist:
#                 raise serializers.ValidationError(
#                     "Nutritionist profile missing. Virtual not allowed."
#                 )

#             if not profile.is_virtual_enabled:
#                 raise serializers.ValidationError(
#                     "Nutritionist does not support virtual appointments."
#                 )
    
#         data['slot'] = slot
#         return data

#     def create(self, validated_data):
#         user = self.context['request'].user
#         slot = validated_data['slot']

#         with transaction.atomic():
#             slot.is_booked = True
#             slot.save()

#             appointment = Appointment.objects.create(
#                 patient=user,
#                 nutritionist=slot.nutritionist,
#                 slot=slot,
#                 appointment_type=validated_data['appointment_type'],
#                 meeting_link=self._generate_meeting_link(validated_data)
#             )
#             appointment_start = timezone.make_aware(
#                 datetime.combine(slot.date, slot.start_time)
#             )

#             AppointmentReminder.objects.bulk_create([
#                 AppointmentReminder(
#                     appointment=appointment,
#                     remind_at=appointment_start - timedelta(hours=24),
#                     reminder_type="24H"
#                 ),
#                 AppointmentReminder(
#                     appointment=appointment,
#                     remind_at=appointment_start - timedelta(hours=2),
#                     reminder_type="2H"
#                 )
#             ])


#         return appointment

#     def _generate_meeting_link(self, data):
#         if data['appointment_type'] == 'VIRTUAL':
#             return f"https://meet.google.com/{uuid.uuid4().hex[:10]}"
#         return None

class AppointmentCreateSerializer(serializers.Serializer):
    slot_id = serializers.IntegerField()
    appointment_category = serializers.ChoiceField(
        choices=["IN_HOUSE", "EXPERT"]
    )
    appointment_type = serializers.ChoiceField(
        choices=["IN_PERSON", "VIRTUAL"]
    )
    expert_id = serializers.IntegerField(
        required=False,
        allow_null=True
    )

    def validate(self, data):
        request = self.context["request"]
        user = request.user

        try:
            slot = AvailabilitySlot.objects.select_related(
                "nutritionist"
            ).get(id=data["slot_id"])
        except AvailabilitySlot.DoesNotExist:
            raise serializers.ValidationError("Invalid slot")

        if slot.is_booked:
            raise serializers.ValidationError("Slot already booked")

        # 🔒 IN-HOUSE FLOW (SYSTEM ASSIGNED)
        if data["appointment_category"] == "IN_HOUSE":
            try:
                assignment = PatientAssignment.objects.select_related(
                    "nutritionist"
                ).get(patient=user)
            except PatientAssignment.DoesNotExist:
                raise serializers.ValidationError(
                    "No in-house nutritionist assigned to this user"
                )

            # Slot MUST belong to assigned nutritionist
            if slot.nutritionist_id != assignment.nutritionist_id:
                raise serializers.ValidationError(
                    "Slot does not belong to your assigned nutritionist"
                )

            # 🚫 Ignore any expert_id sent from frontend
            data["expert_id"] = None

        # 🔒 EXPERT FLOW
        if data["appointment_category"] == "EXPERT":
            if not data.get("expert_id"):
                raise serializers.ValidationError(
                    "Expert must be selected for expert appointment"
                )

        data["slot"] = slot
        return data



    def create(self, validated_data):
        user = self.context["request"].user
        slot = validated_data["slot"]
        category = validated_data["appointment_category"]
        consult_type = "inhouse" if category == "IN_HOUSE" else "expert"

        from subscriptions.utils import get_active_subscription
        subscription = get_active_subscription(user)

        if not subscription:
            raise serializers.ValidationError({
                "consultation_required": True,
                "message": "Koi active subscription nahi hai."
            })

        if consult_type == "inhouse" and subscription.remaining_inhouse <= 0:
            raise serializers.ValidationError({
                "consultation_required": True,  # ✅ Frontend yeh flag check karega
                "consult_type": "inhouse",
                "message": "Inhouse consultations khatam ho gaye hain."
            })

        if consult_type == "expert" and subscription.remaining_expert <= 0:
            raise serializers.ValidationError({
                "consultation_required": True,
                "consult_type": "expert",
                "message": "Expert consultations khatam ho gaye hain."
            })

        consume_consultation(user=user, consult_type=consult_type)
        # ... baaki create code same rahega

        with transaction.atomic():
            slot.is_booked = True
            slot.save()

            if category == "IN_HOUSE":
                assignment = PatientAssignment.objects.select_related(
                    "nutritionist"
                ).get(patient=user)

                nutritionist = assignment.nutritionist
                selected_expert = None
                assigned_by = "SYSTEM"
            else:
                nutritionist = User.objects.get(
                    id=validated_data["expert_id"]
                )
                selected_expert = nutritionist
                assigned_by = "USER"

            appointment = Appointment.objects.create(
                patient=user,
                nutritionist=nutritionist,
                selected_expert=selected_expert,
                slot=slot,
                appointment_category=category,
                appointment_type=validated_data["appointment_type"],
                assigned_by=assigned_by,
            )
            appointment_start = timezone.make_aware(
                datetime.combine(slot.date, slot.start_time)
            )

            AppointmentReminder.objects.bulk_create([
                AppointmentReminder(
                    appointment=appointment,
                    remind_at=appointment_start - timedelta(hours=24),
                    reminder_type="24H"
                ),
                AppointmentReminder(
                    appointment=appointment,
                    remind_at=appointment_start - timedelta(hours=2),
                    reminder_type="2H"
                )
            ])
        return appointment











# class AppointmentListSerializer(serializers.ModelSerializer):
#     slot = AvailabilitySlotSerializer()
#     nutritionist_name = serializers.CharField(
#         source="nutritionist.full_name", read_only=True
#     )

#     class Meta:
#         model = Appointment
#         fields = [
#             "id",
#             "appointment_type",
#             "status",
#             "meeting_link",
#             "created_at",
#             "nutritionist_name",
#             "slot",
#         ]
        # class NutritionistSlotSerializer(serializers.ModelSerializer):
        #     patient_name = serializers.CharField(
        #         source="appointment.patient.full_name",
        #         read_only=True
        #     )
        #     appointment_status = serializers.CharField(
        #         source="appointment.status",
        #         read_only=True
        #     )

        #     class Meta:
        #         model = AvailabilitySlot
        #         fields = [
        #             "id",
        #             "date",
        #             "start_time",
        #             "end_time",
        #             "is_booked",
        #             "patient_name",
        #             "appointment_status",
        #         ]
class NutritionistSlotSerializer(serializers.ModelSerializer):
    patient = serializers.SerializerMethodField()
    appointment = serializers.SerializerMethodField()

    class Meta:
        model = AvailabilitySlot
        fields = [
            "id",
            "date",
            "start_time",
            "end_time",
            "is_booked",
            "patient",
            "appointment",
        ]

    def get_patient(self, obj):
        appt = getattr(obj, "appointment", None)
        if obj.is_booked and appt and appt.patient:
            return {
                "id": appt.patient.id,
                "name": appt.patient.full_name,
                "email": appt.patient.email,
            }
        return None

    def get_appointment(self, obj):
        appt = getattr(obj, "appointment", None)
        if obj.is_booked and appt:
            return {
                "id": appt.id,
                "status": appt.status,
                "type": appt.appointment_type,
                "category": appt.appointment_category,
                "assigned_by": appt.assigned_by,
                "meeting_link": appt.meeting_link,
            }
        return None


class AppointmentListSerializer(serializers.ModelSerializer):
    slot = AvailabilitySlotSerializer()
    nutritionist_name = serializers.CharField(
        source="nutritionist.full_name", read_only=True
    )

    class Meta:
        model = Appointment
        fields = [
            "id",
            "appointment_category",
            "appointment_type",
            "status",
            "assigned_by",
            "meeting_link",
            "created_at",
            "nutritionist_name",
            "slot",
        ]
