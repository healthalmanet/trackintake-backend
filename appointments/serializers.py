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
from .models import AppointmentReminder,AppointmentFeedback
from nutritionist.models import PatientAssignment
from subscriptions.services import consume_consultation
from appointments.zoom_service import create_zoom_meeting
User = get_user_model()


class FeedbackDisplaySerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="given_by.full_name")

    class Meta:
        model = AppointmentFeedback
        fields = ["user_name", "role", "rating", "comment", "created_at"]

# ---------- Slots ----------
class AvailabilitySlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailabilitySlot
        fields = ['id', 'date', 'start_time', 'end_time']


class AvailabilitySlotCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailabilitySlot
        fields = ['date', 'start_time', 'end_time']


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

        
        # ... baaki create code same rahega

        with transaction.atomic():
            slot = AvailabilitySlot.objects.select_for_update().get(id=slot.id)

            if slot.is_booked:
                raise serializers.ValidationError("Slot already booked")

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

            meeting_link = None

# 🔥 ZOOM INTEGRATION
            if validated_data["appointment_type"] == "VIRTUAL":
                try:
                    appointment_start = timezone.make_aware(
                        datetime.combine(slot.date, slot.start_time)
                    )

                    duration = int(
                        (datetime.combine(slot.date, slot.end_time) -
                        datetime.combine(slot.date, slot.start_time)
                        ).total_seconds() / 60
                    )

                    zoom_response = create_zoom_meeting(
                        topic=f"Consultation with {nutritionist.full_name}",
                        start_time_str=appointment_start.isoformat(),
                        duration=duration
                    )

                    if "join_url" not in zoom_response:
                        print("❌ Zoom API Error Response:", zoom_response)
                        raise serializers.ValidationError("Zoom meeting creation failed")

                    meeting_link = zoom_response["join_url"]

                except Exception as e:
                    print("❌ Zoom creation failed:", str(e))
                    raise serializers.ValidationError("Zoom meeting creation failed")

            # ✅ CREATE APPOINTMENT WITH LINK
            appointment = Appointment.objects.create(
                patient=user,
                nutritionist=nutritionist,
                selected_expert=selected_expert,
                slot=slot,
                appointment_category=category,
                appointment_type=validated_data["appointment_type"],
                assigned_by=assigned_by,
                meeting_link=meeting_link
            )
            consume_consultation(user=user, consult_type=consult_type)
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





class AppointmentFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppointmentFeedback
        fields = ["id", "appointment", "rating", "comment", "created_at"]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        appointment = validated_data["appointment"]

        # 🔒 SECURITY CHECK
        if user != appointment.patient and user != appointment.nutritionist:
            raise serializers.ValidationError("Not allowed")

        role = "PATIENT" if user == appointment.patient else "NUTRITIONIST"

        return AppointmentFeedback.objects.create(
            given_by=user,
            role=role,
            **validated_data
        )






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

    feedbacks = FeedbackDisplaySerializer(many=True, read_only=True)

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

                # ✅ ADD THIS
                "feedbacks",
            ]
