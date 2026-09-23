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
    online_price = serializers.SerializerMethodField()
    offline_price = serializers.SerializerMethodField()
    offline_payment_required = serializers.SerializerMethodField()
    offline_location = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()

    class Meta:
        model = AvailabilitySlot
        fields = [
            'id', 'date', 'start_time', 'end_time', 'slot_type', 'is_booked',
            'online_price', 'offline_price', 'offline_payment_required', 'offline_location', 'price'
        ]

    def _get_profile(self, obj):
        profile = self.context.get("nutritionist_profile")
        if profile is not None:
            return profile
        return getattr(obj.nutritionist, "nutritionist_profile", None)

    def get_online_price(self, obj):
        profile = self._get_profile(obj)
        return float(profile.online_price) if profile and profile.online_price is not None else 0.0

    def get_offline_price(self, obj):
        profile = self._get_profile(obj)
        return float(profile.offline_price) if profile and profile.offline_price is not None else 0.0

    def get_offline_payment_required(self, obj):
        profile = self._get_profile(obj)
        return profile.offline_payment_required if profile else True

    def get_offline_location(self, obj):
        profile = self._get_profile(obj)
        return profile.offline_location if profile else ""

    def get_price(self, obj):
        profile = self._get_profile(obj)
        if not profile:
            return 0.0
        if obj.slot_type == "IN_PERSON":
            return float(profile.offline_price or 0.0)
        return float(profile.online_price or 0.0)


class AvailabilitySlotCreateSerializer(serializers.ModelSerializer):
    slot_type = serializers.ChoiceField(
        choices=AvailabilitySlot.SLOT_TYPE,
        default="BOTH",
        required=False,
    )

    class Meta:
        model = AvailabilitySlot
        fields = ['date', 'start_time', 'end_time', 'slot_type']


class AppointmentCreateSerializer(serializers.Serializer):
    slot_id = serializers.IntegerField()
    appointment_category = serializers.ChoiceField(
        choices=["IN_HOUSE", "EXPERT"]
    )
    appointment_type = serializers.ChoiceField(
        choices=["IN_PERSON", "VIRTUAL"],
        default="VIRTUAL",
        required=False
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
                "nutritionist", "nutritionist__nutritionist_profile"
            ).get(id=data["slot_id"])
        except AvailabilitySlot.DoesNotExist:
            raise serializers.ValidationError("Invalid slot")

        if slot.is_booked:
            raise serializers.ValidationError("Slot already booked")

        # 🔒 Check slot type compatibility
        if slot.slot_type != "BOTH" and slot.slot_type != data["appointment_type"]:
            type_label = "In-Clinic" if slot.slot_type == "IN_PERSON" else "Virtual"
            raise serializers.ValidationError(
                f"This slot is reserved for {type_label} appointments."
            )

        # 🔒 IN-HOUSE FLOW (SYSTEM ASSIGNED)
        if data["appointment_category"] == "IN_HOUSE":
            assignment = PatientAssignment.objects.select_related(
                "nutritionist"
            ).filter(patient=user).first()

            if not assignment:
                # Automatically assign the slot's nutritionist to the patient
                assignment = PatientAssignment.objects.create(
                    patient=user,
                    nutritionist=slot.nutritionist
                )
            elif slot.nutritionist_id != assignment.nutritionist_id:
                assignment.nutritionist = slot.nutritionist
                assignment.save(update_fields=["nutritionist"])

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
        appointment_type = validated_data.get("appointment_type", "VIRTUAL")
        consult_type = "inhouse" if category == "IN_HOUSE" else "expert"

        nutri_profile = getattr(slot.nutritionist, "nutritionist_profile", None)

        # Determine real price from nutritionist profile
        real_price = 0.0
        if nutri_profile:
            if appointment_type == "IN_PERSON":
                real_price = float(nutri_profile.offline_price or 0.0)
            else:
                real_price = float(nutri_profile.online_price or 0.0)

        offline_payment_required = getattr(nutri_profile, "offline_payment_required", True) if nutri_profile else True

        # Check if offline payment is allowed later (at clinic / cash)
        is_offline_pay_later = (appointment_type == "IN_PERSON" and not offline_payment_required)

        from subscriptions.utils import get_active_subscription
        subscription = get_active_subscription(user)

        consumed_quota = False

        # If user has an active subscription with quota, consume quota
        if subscription:
            if consult_type == "inhouse" and subscription.remaining_inhouse > 0:
                consumed_quota = True
            elif consult_type == "expert" and subscription.remaining_expert > 0:
                consumed_quota = True

        # If user does NOT have quota, AND upfront payment IS required (not offline pay-later and real_price > 0):
        if not consumed_quota and not is_offline_pay_later and real_price > 0:
            raise serializers.ValidationError({
                "consultation_required": True,
                "consult_type": consult_type,
                "price": real_price,
                "appointment_type": appointment_type,
                "offline_payment_required": offline_payment_required,
                "message": f"Payment of ₹{real_price} is required to book this {appointment_type.lower()} consultation."
            })

        with transaction.atomic():
            slot = AvailabilitySlot.objects.select_for_update().get(id=slot.id)

            if slot.is_booked:
                raise serializers.ValidationError("Slot already booked")

            slot.is_booked = True
            slot.save()

            if category == "IN_HOUSE":
                assignment = PatientAssignment.objects.select_related(
                    "nutritionist"
                ).filter(patient=user).first()

                if assignment:
                    nutritionist = assignment.nutritionist
                else:
                    nutritionist = slot.nutritionist

                selected_expert = None
                assigned_by = "SYSTEM"
            else:
                nutritionist = User.objects.get(
                    id=validated_data["expert_id"]
                )
                selected_expert = nutritionist
                assigned_by = "USER"

            meeting_link = None

            # 🔥 ZOOM INTEGRATION (Virtual Consultation Link Generated at Booking Time)
            if appointment_type == "VIRTUAL":
                try:
                    appointment_start = timezone.make_aware(
                        datetime.combine(slot.date, slot.start_time)
                    )

                    duration = int(
                        (datetime.combine(slot.date, slot.end_time) -
                        datetime.combine(slot.date, slot.start_time)
                        ).total_seconds() / 60
                    )

                    patient_name = getattr(user, "full_name", "") or getattr(user, "email", "Patient")
                    nutritionist_name = getattr(nutritionist, "full_name", "") or "Nutritionist"

                    zoom_response = create_zoom_meeting(
                        topic=f"Consultation: {patient_name} with {nutritionist_name}",
                        start_time_str=appointment_start.isoformat(),
                        duration=duration
                    )

                    meeting_link = zoom_response.get("join_url")
                except Exception as e:
                    print(f"⚠️ Zoom link generation error: {e}")
                    meeting_link = f"https://zoom.us/j/trackintake-{slot.id}"

            # ✅ CREATE APPOINTMENT WITH LINK
            appointment = Appointment.objects.create(
                patient=user,
                nutritionist=nutritionist,
                selected_expert=selected_expert,
                slot=slot,
                appointment_category=category,
                appointment_type=appointment_type,
                assigned_by=assigned_by,
                meeting_link=meeting_link
            )

            if consumed_quota:
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
    online_price = serializers.SerializerMethodField()
    offline_price = serializers.SerializerMethodField()
    offline_payment_required = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()

    class Meta:
        model = AvailabilitySlot
        fields = [
            "id",
            "date",
            "start_time",
            "end_time",
            "slot_type",
            "is_booked",
            "patient",
            "appointment",
            "online_price",
            "offline_price",
            "offline_payment_required",
            "price",
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
            feedbacks = FeedbackDisplaySerializer(appt.feedbacks.all(), many=True).data
            return {
                "id": appt.id,
                "status": appt.status,
                "type": appt.appointment_type,
                "category": appt.appointment_category,
                "assigned_by": appt.assigned_by,
                "meeting_link": appt.meeting_link,
                "notes": getattr(appt, "notes", ""),
                "instructions": getattr(appt, "instructions", ""),
                "feedbacks": feedbacks,
            }
        return None

    def _get_profile(self, obj):
        profile = self.context.get("nutritionist_profile")
        if profile is not None:
            return profile
        return getattr(obj.nutritionist, "nutritionist_profile", None)

    def get_online_price(self, obj):
        profile = self._get_profile(obj)
        return float(profile.online_price) if profile and profile.online_price is not None else 0.0

    def get_offline_price(self, obj):
        profile = self._get_profile(obj)
        return float(profile.offline_price) if profile and profile.offline_price is not None else 0.0

    def get_offline_payment_required(self, obj):
        profile = self._get_profile(obj)
        return profile.offline_payment_required if profile else True

    def get_price(self, obj):
        profile = self._get_profile(obj)
        if not profile:
            return 0.0
        if obj.slot_type == "IN_PERSON":
            return float(profile.offline_price or 0.0)
        return float(profile.online_price or 0.0)


class AppointmentListSerializer(serializers.ModelSerializer):
    slot = AvailabilitySlotSerializer()
    nutritionist_name = serializers.CharField(
        source="nutritionist.full_name", read_only=True
    )
    nutritionist_email = serializers.CharField(
        source="nutritionist.email", read_only=True
    )
    patient_id = serializers.IntegerField(
        source="patient.id", read_only=True
    )
    patient_name = serializers.CharField(
        source="patient.full_name", read_only=True
    )
    patient_email = serializers.CharField(
        source="patient.email", read_only=True
    )
    offline_location = serializers.SerializerMethodField()
    online_price = serializers.SerializerMethodField()
    offline_price = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    offline_payment_required = serializers.SerializerMethodField()
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
            "notes",
            "instructions",
            "created_at",
            "patient_id",
            "patient_name",
            "patient_email",
            "nutritionist_name",
            "nutritionist_email",
            "offline_location",
            "online_price",
            "offline_price",
            "price",
            "offline_payment_required",
            "slot",
            "feedbacks",
        ]

    def get_offline_location(self, obj):
        profile = getattr(obj.nutritionist, "nutritionist_profile", None)
        return profile.offline_location if profile else ""

    def get_online_price(self, obj):
        profile = getattr(obj.nutritionist, "nutritionist_profile", None)
        return float(profile.online_price) if profile and profile.online_price is not None else 0.0

    def get_offline_price(self, obj):
        profile = getattr(obj.nutritionist, "nutritionist_profile", None)
        return float(profile.offline_price) if profile and profile.offline_price is not None else 0.0

    def get_price(self, obj):
        profile = getattr(obj.nutritionist, "nutritionist_profile", None)
        if not profile:
            return 0.0
        if obj.appointment_type == "IN_PERSON":
            return float(profile.offline_price or 0.0)
        return float(profile.online_price or 0.0)

    def get_offline_payment_required(self, obj):
        profile = getattr(obj.nutritionist, "nutritionist_profile", None)
        return profile.offline_payment_required if profile else True


class AppointmentDetailSerializer(serializers.ModelSerializer):
    slot = AvailabilitySlotSerializer()
    patient_details = serializers.SerializerMethodField()
    nutritionist_details = serializers.SerializerMethodField()
    feedbacks = FeedbackDisplaySerializer(many=True, read_only=True)
    price = serializers.SerializerMethodField()
    offline_payment_required = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            "id",
            "appointment_category",
            "appointment_type",
            "status",
            "assigned_by",
            "meeting_link",
            "notes",
            "instructions",
            "created_at",
            "slot",
            "price",
            "offline_payment_required",
            "patient_details",
            "nutritionist_details",
            "feedbacks",
        ]

    def get_price(self, obj):
        profile = getattr(obj.nutritionist, "nutritionist_profile", None)
        if not profile:
            return 0.0
        if obj.appointment_type == "IN_PERSON":
            return float(profile.offline_price or 0.0)
        return float(profile.online_price or 0.0)

    def get_offline_payment_required(self, obj):
        profile = getattr(obj.nutritionist, "nutritionist_profile", None)
        return profile.offline_payment_required if profile else True

    def get_patient_details(self, obj):
        p = obj.patient
        profile = getattr(p, "user_profile", None) or getattr(p, "profile", None)
        return {
            "id": p.id,
            "name": p.full_name or p.username,
            "email": p.email,
            "phone": getattr(profile, "phone_number", None) or getattr(p, "phone_number", "") or "",
            "gender": getattr(profile, "gender", "") or "",
            "age": getattr(profile, "age", "") or "",
            "goal": getattr(profile, "health_goal", "") or getattr(profile, "goal", "") or "",
            "allergies": getattr(profile, "allergies", []) if profile else [],
            "medical_conditions": getattr(profile, "medical_conditions", []) if profile else [],
        }

    def get_nutritionist_details(self, obj):
        n = obj.nutritionist
        profile = getattr(n, "nutritionist_profile", None)
        return {
            "id": n.id,
            "name": n.full_name or n.username,
            "email": n.email,
            "professional_title": getattr(profile, "professional_title", "Clinical Nutritionist") if profile else "Clinical Nutritionist",
            "qualification": getattr(profile, "qualification", "") if profile else "",
            "years_of_experience": getattr(profile, "years_of_experience", 0) if profile else 0,
            "offline_location": getattr(profile, "offline_location", "") if profile else "",
            "online_price": float(profile.online_price) if profile and profile.online_price is not None else 0.0,
            "offline_price": float(profile.offline_price) if profile and profile.offline_price is not None else 0.0,
        }


class AppointmentNotesUpdateSerializer(serializers.ModelSerializer):
    notes = serializers.CharField(required=False, allow_blank=True)
    instructions = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Appointment
        fields = ["notes", "instructions"]


