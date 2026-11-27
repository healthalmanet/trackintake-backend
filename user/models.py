from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.conf import settings  # ✅ Use this for referencing the user model

# ---------------------- User Manager ----------------------
# class UserManager(BaseUserManager):
#     def create_user(self, email, full_name, password=None):
#         if not email:
#             raise ValueError("Email is required")
#         if not full_name:
#             raise ValueError("Full name is required")
#         user = self.model(email=self.normalize_email(email), full_name=full_name)
#         user.set_password(password)
#         user.save(using=self._db)
#         return user

#     def create_superuser(self, email, full_name, password=None):
#         user = self.create_user(email, full_name, password)
#         user.is_admin = True
#         user.save(using=self._db)
#         return user


class UserManager(BaseUserManager):
    # Add 'role' as an argument with a default value
    def create_user(self, email, full_name, password=None, role="user", phone_number=None):
        if not email:
            raise ValueError("Email is required")
        if not full_name:
            raise ValueError("Full name is required")
        
        user = self.model(
            email=self.normalize_email(email).lower(),
            full_name=full_name,
            phone_number=phone_number,
            role=role
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name, password=None):
        user = self.create_user(
            email,
            full_name,
            password,
            role="admin"
        )
        user.is_admin = True
        user.save(using=self._db)
        return user




# ---------------------- Custom User Model ----------------------
class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ("user", "Normal User (Patient)"),
        ("nutritionist", "Nutritionist"),
        ("admin", "Admin"),
        ("owner", "Owner"),
        ("operator", "Operator"),
    ]

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    date_joined = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    is_blocked = models.BooleanField(default=False)
    blocked_reason = models.TextField(blank=True, null=True)
    blocked_at = models.DateTimeField(blank=True, null=True)
    is_admin = models.BooleanField(default=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="user")

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    def __str__(self):
        return f"{self.full_name} ({self.email} - {self.role})"

    def has_perm(self, perm, obj=None):
        return self.is_admin or self.role == 'admin'

    def has_module_perms(self, app_label):
        return self.is_admin or self.role == 'admin'

    @property
    def is_staff(self):
        return self.is_admin or self.role in ['admin', 'owner']

# ---------------------- Feedback Model ----------------------
class Feedback(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # ✅ Use settings.AUTH_USER_MODEL
    message = models.TextField()
    rating = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback by {self.user.email} - {self.rating}⭐"

# ---------------------- Model Retrain Log ----------------------
class ModelRetrainLog(models.Model):
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    feedbacks_used = models.IntegerField(default=0)
    accuracy_score = models.FloatField(null=True, blank=True)
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # ✅ Fix here too
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )


# ---------------------- Email OTP Verification Model ----------------------
class EmailOTP(models.Model):
    """
    Persistent store for email OTPs and verification tokens.
    Guarantees cross-worker, multi-dyno consistency across all Gunicorn processes.
    """
    email = models.EmailField(db_index=True)
    otp = models.CharField(max_length=6)
    verification_token = models.CharField(max_length=128, blank=True, null=True, db_index=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = "Email OTP"
        verbose_name_plural = "Email OTPs"
        indexes = [
            models.Index(fields=["email", "otp"]),
            models.Index(fields=["email", "verification_token"]),
            models.Index(fields=["email", "-created_at"]),
        ]

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"{self.email} - {self.otp} (verified={self.is_verified})"


# ---------------------- Blocked Contact Registry ----------------------
class BlockedContact(models.Model):
    """
    Persistent registry of blocked emails (including canonicalized Gmail addresses)
    and mobile/phone numbers so blocked users cannot re-register under any variation.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="block_records",
    )
    email = models.EmailField(blank=True, null=True, db_index=True)
    canonical_email = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    phone_number = models.CharField(max_length=32, blank=True, null=True, db_index=True)
    phone_last10 = models.CharField(max_length=10, blank=True, null=True, db_index=True)
    reason = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Blocked Contact"
        verbose_name_plural = "Blocked Contacts"
        indexes = [
            models.Index(fields=["is_active", "email"]),
            models.Index(fields=["is_active", "canonical_email"]),
            models.Index(fields=["is_active", "phone_number"]),
            models.Index(fields=["is_active", "phone_last10"]),
        ]

    def save(self, *args, **kwargs):
        from .blocking import canonicalize_email, normalize_email, normalize_phone

        if self.email:
            self.email = normalize_email(self.email)
            self.canonical_email = canonicalize_email(self.email)
        else:
            self.email = None
            if self.canonical_email:
                self.canonical_email = canonicalize_email(self.canonical_email)

        if self.phone_number:
            digits, last10 = normalize_phone(self.phone_number)
            self.phone_number = digits or None
            self.phone_last10 = last10 or None
        else:
            self.phone_number = None
            self.phone_last10 = None

        super().save(*args, **kwargs)

    def __str__(self):
        parts = [p for p in [self.email, self.phone_number] if p]
        target = " / ".join(parts) if parts else f"Record #{self.pk}"
        status_label = "ACTIVE" if self.is_active else "INACTIVE"
        return f"{target} [{status_label}]"
