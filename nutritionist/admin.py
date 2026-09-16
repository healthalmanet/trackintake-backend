from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import NutritionistProfile


@admin.register(NutritionistProfile)
class NutritionistProfileAdmin(admin.ModelAdmin):
    list_display = (
        "get_photo_thumbnail",
        "user",
        "get_full_name",
        "get_email",
        "is_verified",
        "price_approval_status",
        "is_online_available",
        "online_price",
        "is_offline_available",
        "offline_price",
        "get_documents_count",
        "created_at",
    )
    list_filter = (
        "price_approval_status",
        "is_verified",
        "is_online_available",
        "is_offline_available",
        "offline_payment_required",
        "nutritionist_type",
        "created_at",
    )
    search_fields = ("user__email", "user__full_name", "user__phone_number", "offline_location")
    list_editable = ("is_verified",)
    readonly_fields = (
        "verified_at",
        "created_at",
        "updated_at",
        "profile_photo_preview",
        "qualification_cert_preview",
        "registration_cert_preview",
        "government_id_preview",
        "experience_cert_preview",
        "additional_certs_preview",
    )
    fieldsets = (
        ("Practitioner Account & Verification Status", {
            "fields": (
                "user",
                "nutritionist_type",
                "is_verified",
                "verified_at",
                "created_at",
                "updated_at",
            )
        }),
        ("Appointment Availability & Practice Rates", {
            "fields": (
                "is_online_available",
                "online_price",
                "pending_online_price",
                "is_offline_available",
                "offline_price",
                "pending_offline_price",
                "offline_location",
                "offline_payment_required",
                "pending_offline_payment_required",
                "price_approval_status",
                "price_rejection_reason",
            )
        }),
        ("Professional Credentials & Bio", {
            "fields": (
                "professional_title",
                "qualification",
                "registration_number",
                "issuing_authority",
                "years_of_experience",
                "current_organization",
                "languages_spoken",
                "specializations",
                "professional_bio",
            )
        }),
        ("Verification Documents & Profile Photo", {
            "fields": (
                "profile_photo",
                "profile_photo_preview",
                "qualification_certificate",
                "qualification_cert_preview",
                "registration_certificate",
                "registration_cert_preview",
                "government_id",
                "government_id_preview",
                "experience_certificate",
                "experience_cert_preview",
                "additional_certifications",
                "additional_certs_preview",
            )
        }),
    )
    actions = [
        "verify_nutritionists",
        "unverify_nutritionists",
        "approve_pricing_requests",
        "reject_pricing_requests",
    ]

    @admin.display(description="Photo")
    def get_photo_thumbnail(self, obj):
        if obj.profile_photo:
            return format_html(
                '<img src="{}" style="width:36px; height:36px; border-radius:50%; object-fit:cover; border:2px solid #0ea5e9;" />',
                obj.profile_photo.url
            )
        return format_html('<span style="color:#94a3b8; font-size:11px;">No Photo</span>')

    @admin.display(description="Docs Uploaded")
    def get_documents_count(self, obj):
        docs = [
            obj.qualification_certificate,
            obj.registration_certificate,
            obj.government_id,
            obj.experience_certificate,
            obj.additional_certifications,
        ]
        uploaded = sum(1 for d in docs if bool(d))
        return format_html(
            '<span style="padding:3px 8px; border-radius:10px; font-weight:bold; font-size:11px; background:{}; color:white;">{}/5 Docs</span>',
            "#10b981" if uploaded > 0 else "#94a3b8",
            uploaded
        )

    @admin.display(description="Profile Photo Preview")
    def profile_photo_preview(self, obj):
        if obj.profile_photo:
            return format_html(
                '<div style="display:flex; align-items:center; gap:12px;">'
                '<img src="{}" style="width:90px; height:90px; border-radius:12px; object-fit:cover; border:2px solid #0ea5e9;" />'
                '<a href="{}" target="_blank" style="padding:6px 14px; background:#0ea5e9; color:white; border-radius:8px; text-decoration:none; font-weight:bold; font-size:12px;">🔍 View Full Photo</a>'
                '</div>',
                obj.profile_photo.url,
                obj.profile_photo.url
            )
        return format_html('<span style="color:#94a3b8;">No profile photo uploaded.</span>')

    @admin.display(description="Qualification Certificate Preview")
    def qualification_cert_preview(self, obj):
        if obj.qualification_certificate:
            return format_html(
                '<a href="{}" target="_blank" style="display:inline-flex; align-items:center; gap:6px; padding:7px 14px; background:#0284c7; color:white; border-radius:8px; text-decoration:none; font-weight:bold; font-size:12px;">'
                '📄 Open Qualification Certificate</a>',
                obj.qualification_certificate.url
            )
        return format_html('<span style="color:#94a3b8;">Not uploaded.</span>')

    @admin.display(description="Registration Certificate Preview")
    def registration_cert_preview(self, obj):
        if obj.registration_certificate:
            return format_html(
                '<a href="{}" target="_blank" style="display:inline-flex; align-items:center; gap:6px; padding:7px 14px; background:#0284c7; color:white; border-radius:8px; text-decoration:none; font-weight:bold; font-size:12px;">'
                '📄 Open Registration Certificate</a>',
                obj.registration_certificate.url
            )
        return format_html('<span style="color:#94a3b8;">Not uploaded.</span>')

    @admin.display(description="Government ID Proof Preview")
    def government_id_preview(self, obj):
        if obj.government_id:
            return format_html(
                '<a href="{}" target="_blank" style="display:inline-flex; align-items:center; gap:6px; padding:7px 14px; background:#0284c7; color:white; border-radius:8px; text-decoration:none; font-weight:bold; font-size:12px;">'
                '📄 Open Government ID Proof</a>',
                obj.government_id.url
            )
        return format_html('<span style="color:#94a3b8;">Not uploaded.</span>')

    @admin.display(description="Experience Certificate Preview")
    def experience_cert_preview(self, obj):
        if obj.experience_certificate:
            return format_html(
                '<a href="{}" target="_blank" style="display:inline-flex; align-items:center; gap:6px; padding:7px 14px; background:#0284c7; color:white; border-radius:8px; text-decoration:none; font-weight:bold; font-size:12px;">'
                '📄 Open Experience Certificate</a>',
                obj.experience_certificate.url
            )
        return format_html('<span style="color:#94a3b8;">Not uploaded.</span>')

    @admin.display(description="Additional Certifications Preview")
    def additional_certs_preview(self, obj):
        if obj.additional_certifications:
            return format_html(
                '<a href="{}" target="_blank" style="display:inline-flex; align-items:center; gap:6px; padding:7px 14px; background:#0284c7; color:white; border-radius:8px; text-decoration:none; font-weight:bold; font-size:12px;">'
                '📄 Open Additional Certifications</a>',
                obj.additional_certifications.url
            )
        return format_html('<span style="color:#94a3b8;">Not uploaded.</span>')

    @admin.display(description="Full Name")
    def get_full_name(self, obj):
        return obj.user.full_name or "N/A"

    @admin.display(description="Email")
    def get_email(self, obj):
        return obj.user.email

    @admin.display(description="Phone Number")
    def get_phone_number(self, obj):
        return obj.user.phone_number or "N/A"

    @admin.action(description="✅ Verify selected nutritionists")
    def verify_nutritionists(self, request, queryset):
        from features.models import Message
        from features.tasks import send_message_notification

        now = timezone.now()
        count = 0
        for profile in queryset:
            profile.is_verified = True
            profile.verified_at = now
            profile.save()
            count += 1

            # Dispatch persistent notification to nutritionist
            msg_text = (
                "🎉 Congratulations! Your practitioner profile has been officially VERIFIED & APPROVED by TrackIntake Admin. "
                "Your clinical credentials and consultation services are now active and live for patients."
            )
            message_obj = Message.objects.create(
                sender=request.user,
                receiver=profile.user,
                text=msg_text
            )
            try:
                send_message_notification(message_obj)
            except Exception as e:
                print(f"Failed to send verification notification: {e}")

        self.message_user(request, f"{count} nutritionist(s) verified successfully and notifications sent.")

    @admin.action(description="❌ Unverify selected nutritionists")
    def unverify_nutritionists(self, request, queryset):
        from features.models import Message
        from features.tasks import send_message_notification

        count = 0
        for profile in queryset:
            profile.is_verified = False
            profile.verified_at = None
            profile.save()
            count += 1

            # Dispatch notification
            msg_text = (
                "⚠️ Your practitioner account verification status has been revoked by Admin. "
                "Please check your uploaded verification documents or contact support."
            )
            message_obj = Message.objects.create(
                sender=request.user,
                receiver=profile.user,
                text=msg_text
            )
            try:
                send_message_notification(message_obj)
            except Exception as e:
                print(f"Failed to send un-verification notification: {e}")

        self.message_user(request, f"{count} nutritionist(s) unverified.")

    def save_model(self, request, obj, form, change):
        from features.models import Message
        from features.tasks import send_message_notification

        old_obj = None
        if change and obj.pk:
            try:
                old_obj = NutritionistProfile.objects.get(pk=obj.pk)
            except NutritionistProfile.DoesNotExist:
                pass

        super().save_model(request, obj, form, change)

        if old_obj:
            # Check if verification status changed to verified
            if not old_obj.is_verified and obj.is_verified:
                msg_text = (
                    "🎉 Congratulations! Your practitioner profile has been officially VERIFIED & APPROVED by TrackIntake Admin. "
                    "Your clinical credentials and consultation services are now active and live."
                )
                message_obj = Message.objects.create(
                    sender=request.user,
                    receiver=obj.user,
                    text=msg_text
                )
                try:
                    send_message_notification(message_obj)
                except Exception as e:
                    print(f"Failed to send verification notification on save: {e}")

            # Check if price approval status changed to approved
            if old_obj.price_approval_status != "approved" and obj.price_approval_status == "approved":
                if obj.pending_online_price is not None:
                    obj.online_price = obj.pending_online_price
                    obj.pending_online_price = None
                if obj.pending_offline_price is not None:
                    obj.offline_price = obj.pending_offline_price
                    obj.pending_offline_price = None
                if obj.pending_offline_payment_required is not None:
                    obj.offline_payment_required = obj.pending_offline_payment_required
                    obj.pending_offline_payment_required = None
                obj.price_rejection_reason = None
                obj.save(update_fields=['online_price', 'offline_price', 'offline_payment_required', 'pending_online_price', 'pending_offline_price', 'pending_offline_payment_required', 'price_rejection_reason'])

                msg_text = (
                    f"🎉 Your appointment pricing has been APPROVED by Admin! "
                    f"Online Price: ₹{obj.online_price}, Offline Price: ₹{obj.offline_price}."
                )
                message_obj = Message.objects.create(
                    sender=request.user,
                    receiver=obj.user,
                    text=msg_text
                )
                try:
                    send_message_notification(message_obj)
                except Exception as e:
                    print(f"Failed to send price approval notification on save: {e}")

    @admin.action(description="💰 Approve selected pricing requests")
    def approve_pricing_requests(self, request, queryset):
        from features.models import Message
        from features.tasks import send_message_notification

        count = 0
        for profile in queryset:
            if profile.pending_online_price is not None:
                profile.online_price = profile.pending_online_price
            if profile.pending_offline_price is not None:
                profile.offline_price = profile.pending_offline_price
            if profile.pending_offline_payment_required is not None:
                profile.offline_payment_required = profile.pending_offline_payment_required

            profile.pending_online_price = None
            profile.pending_offline_price = None
            profile.pending_offline_payment_required = None
            profile.price_approval_status = "approved"
            profile.price_rejection_reason = None
            profile.save()

            count += 1
            # Dispatch notification
            msg_text = (
                f"🎉 Your appointment pricing has been APPROVED by Admin! "
                f"Online Price: ₹{profile.online_price}, Offline Price: ₹{profile.offline_price}."
            )
            message_obj = Message.objects.create(
                sender=request.user,
                receiver=profile.user,
                text=msg_text
            )
            try:
                send_message_notification(message_obj)
            except Exception as e:
                print(f"Failed to send notification: {e}")

        self.message_user(request, f"Approved pricing for {count} nutritionist(s) and sent notifications.")

    @admin.action(description="🚫 Reject selected pricing requests")
    def reject_pricing_requests(self, request, queryset):
        from features.models import Message
        from features.tasks import send_message_notification

        count = 0
        for profile in queryset:
            profile.price_approval_status = "rejected"
            profile.price_rejection_reason = "Rejected by admin from admin panel."
            profile.pending_online_price = None
            profile.pending_offline_price = None
            profile.pending_offline_payment_required = None
            profile.save()

            count += 1
            # Dispatch notification
            msg_text = "⚠️ Your appointment pricing request was REJECTED by Admin."
            message_obj = Message.objects.create(
                sender=request.user,
                receiver=profile.user,
                text=msg_text
            )
            try:
                send_message_notification(message_obj)
            except Exception as e:
                print(f"Failed to send notification: {e}")

        self.message_user(request, f"Rejected pricing for {count} nutritionist(s) and sent notifications.")