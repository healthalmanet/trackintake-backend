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
    def create_user(self, email, full_name, password=None, role="user"):
        if not email:
            raise ValueError("Email is required")
        if not full_name:
            raise ValueError("Full name is required")
        
        # Add the 'role' when creating the model instance
        user = self.model(
            email=self.normalize_email(email).lower(),
            full_name=full_name,
            role=role  # <-- ADD THIS LINE
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name, password=None):
        # When creating a superuser, we can explicitly set the role
        user = self.create_user(
            email,
            full_name,
            password,
            role="admin"  # <-- Recommended: Explicitly set the superuser role
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
    date_joined = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
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
