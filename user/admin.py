# from django.contrib import admin
# from django import forms
# from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
# from django.contrib.auth.forms import ReadOnlyPasswordHashField



# from .models import  User, Feedback
# from features.models import Blog, CustomReminder, WaterIntakeLog, WeightLog, Message
# from owner.models import AppReport
# from nutritionist.models import NutritionistProfile,PatientAssignment
# from diet.models import DietRecommendation, DietFeedback
# from  userFood.models import UserMeal,FoodItem
# from userProfile.models import LabReport,UserProfile


# # ------------------------------
# # Custom User Creation Form (for Admin 'Add User' Page)
# # ------------------------------
# class CustomUserCreationForm(forms.ModelForm):
#     password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
#     password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput)

#     class Meta:
#         model = User
#         fields = ("email", "full_name", "role")

#     def clean_password2(self):
#         password1 = self.cleaned_data.get("password1")
#         password2 = self.cleaned_data.get("password2")
#         if password1 and password2 and password1 != password2:
#             raise forms.ValidationError("Passwords don't match")
#         return password2

#     def save(self, commit=True):
#         user = super().save(commit=False)
#         user.set_password(self.cleaned_data["password1"])
#         if commit:
#             user.save()
#         return user

# # ------------------------------
# # Custom User Change Form (for editing users in Admin)
# # ------------------------------
# class CustomUserChangeForm(forms.ModelForm):
#     password = ReadOnlyPasswordHashField()

#     class Meta:
#         model = User
#         fields = ("email", "full_name", "role", "is_active", "is_admin")

# # ------------------------------
# # Custom User Admin Configuration
# # ------------------------------
# class CustomUserAdmin(BaseUserAdmin):
#     form = CustomUserChangeForm
#     add_form = CustomUserCreationForm

#     list_display = ("email", "full_name", "role", "is_active", "is_admin")
#     list_filter = ("role", "is_admin")

#     fieldsets = (
#         (None, {"fields": ("email", "password")}),
#         ("Personal Info", {"fields": ("full_name",)}),
#         ("Permissions", {"fields": ("role", "is_active", "is_admin")}),
#     )

#     add_fieldsets = (
#         (None, {
#             "classes": ("wide",),
#             "fields": ("email", "full_name", "role", "password1", "password2"),
#         }),
#     )

#     search_fields = ("email", "full_name")
#     ordering = ("email",)
#     filter_horizontal = ()

# @admin.register(FoodItem)
# class FoodItemAdmin(admin.ModelAdmin):
#     list_display = (
#         "name", "calories", "protein", "carbs", "fats",
#         "fodmap_level", "spice_level", "purine_level", "is_verified"
#     )
#     list_filter = ("fodmap_level", "spice_level", "purine_level", "is_verified")
#     search_fields = ("name",)
#     filter_horizontal = ("food_types", "meal_types", "allergens")



# # ------------------------------
# # Patient Assignment
# # ------------------------------
# @admin.register(PatientAssignment)
# class PatientAssignmentAdmin(admin.ModelAdmin):
#     """
#     Custom admin view for Patient Assignments.
#     """
#     # Fields to display in the main list view
#     list_display = ('patient', 'nutritionist', 'assigned_at')

#     # Fields to search by
#     search_fields = ('patient__username', 'patient__first_name', 'patient__last_name', 'nutritionist__username')
    
#     # Filters on the right-hand side
#     list_filter = ('nutritionist', 'assigned_at')
    
#     # The autocomplete_fields are crucial for models with many users.
#     autocomplete_fields = ['patient', 'nutritionist'] 

#     # Defines the order of fields when adding/editing a record
#     fieldsets = (
#         (None, {
#             'fields': ('patient', 'nutritionist', 'assigned_at')
#         }),
#     )

#     def get_form(self, request, obj=None, **kwargs):
#         """
#         Override get_form to filter the 'patient' field queryset.
#         This ensures that only unassigned patients are shown when creating
#         a new assignment.
#         """
#         # Get the default form created by the parent class
#         form = super().get_form(request, obj, **kwargs)

#         # Get all patient IDs that are already in an assignment.
#         # We use values_list with flat=True to get a simple list like [1, 5, 10]
#         assigned_patient_ids = PatientAssignment.objects.values_list('patient_id', flat=True)

#         # Start with a queryset of all potential patients (e.g., all users).
#         # You might want to filter this further, e.g., for users in a 'Patient' group.
#         # For now, we assume any user can be a patient.
#         patient_queryset = User.objects.all()

#         if obj:
#             # This is the 'change' form (editing an existing assignment).
#             # We must EXCLUDE all assigned patients EXCEPT for the one
#             # currently being edited. Otherwise, the current patient wouldn't
#             # appear in the dropdown, which would be confusing.
#             patient_queryset = patient_queryset.exclude(
#                 id__in=assigned_patient_ids
#             ).union(User.objects.filter(pk=obj.patient_id))
#             # The .union() or '|' operator adds the current patient back to the choices.
#             # A simpler way using | operator:
#             # form.base_fields['patient'].queryset = (
#             #     User.objects.exclude(id__in=assigned_patient_ids) | 
#             #     User.objects.filter(pk=obj.patient_id)
#             # )

#         else:
#             # This is the 'add' form (creating a new assignment).
#             # We simply EXCLUDE all patients who are already assigned.
#             patient_queryset = patient_queryset.exclude(id__in=assigned_patient_ids)

#         # Apply the final filtered queryset to the 'patient' field on the form.
#         form.base_fields['patient'].queryset = patient_queryset

#         return form

#     # Automatically sets the nutritionist to the currently logged-in user if they are a nutritionist
#     def save_model(self, request, obj, form, change):
#         if not obj.pk and not obj.nutritionist_id:
#             # Only set on creation if nutritionist is not already chosen
#             if request.user.groups.filter(name='Nutritionist').exists():
#                 obj.nutritionist = request.user
#         super().save_model(request, obj, form, change)
# # ------------------------------
# # Register Models with Admin
# # ------------------------------
# admin.site.register(User, CustomUserAdmin)
# admin.site.register(UserProfile)
# # admin.site.register(DiabeticProfile)
# admin.site.register(LabReport)
# admin.site.register(UserMeal)
# # admin.site.register(Feedback)
# admin.site.register(CustomReminder)
# admin.site.register(NutritionistProfile)
# admin.site.register(DietRecommendation)
# # admin.site.register(PatientAssignment)
# # admin.site.register(AppReport)
# # admin.site.register(DietFeedback)
# admin.site.register(Blog)
# admin.site.register(Message)
# admin.site.register(WeightLog)
# admin.site.register(WaterIntakeLog)



import re
from django.contrib import admin
from django import forms
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField

# Your model imports
from .models import User, Feedback
from features.models import Blog, CustomReminder, WaterIntakeLog, WeightLog, Message
from owner.models import AppReport
from nutritionist.models import NutritionistProfile, PatientAssignment
from diet.models import DietRecommendation, DietFeedback
from userFood.models import UserMeal, FoodItem
from userProfile.models import LabReport, UserProfile


# ------------------------------
# Custom User Creation Form (for Admin 'Add User' Page)
# ------------------------------
class CustomUserCreationForm(forms.ModelForm):
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("email", "full_name", "role")

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user

# ------------------------------
# Custom User Change Form (for editing users in Admin)
# ------------------------------
class CustomUserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField()

    class Meta:
        model = User
        fields = ("email", "full_name", "role", "is_active", "is_admin")

# ------------------------------
# Custom User Admin Configuration
# ------------------------------
class CustomUserAdmin(BaseUserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display = ("email", "full_name", "role", "date_joined", "is_active", "is_admin")
    list_filter = ("role", "is_admin", "date_joined")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal Info", {"fields": ("full_name",)}),
        ("Permissions", {
            "fields": (
                "role",
                "is_active",
                "is_admin",
                "groups",               # ✅ Allow assigning groups
                "user_permissions"      # ✅ Allow assigning specific permissions
            )
        }),
        ("Important Dates", {"fields": ("date_joined", "last_login")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "full_name", "role", "password1", "password2", "groups"),
        }),
    )

    search_fields = ("email", "full_name")
    ordering = ("-date_joined",)
    filter_horizontal = ("groups", "user_permissions")  # ✅ Nice multi-select UI
    readonly_fields = ('date_joined', 'last_login')

    def get_search_results(self, request, queryset, search_term):
        """
        THIS IS THE CORRECT IMPLEMENTATION.
        It filters autocomplete results for Users.
        """
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)

        # We only apply this special filtering if the autocomplete request
        # is coming from the PatientAssignment form.
        if request.GET.get('model_name') == 'patientassignment':
            
            # Get all patient IDs that are already in an assignment
            assigned_patient_ids = list(PatientAssignment.objects.values_list('patient_id', flat=True))

            # On the "change" form, we must allow the currently selected patient to appear.
            # We determine this by checking the page URL that made the request.
            referer = request.META.get('HTTP_REFERER')
            if referer:
                match = re.search(r'/patientassignment/(\d+)/change', referer)
                if match:
                    try:
                        assignment_id = match.group(1)
                        assignment_being_edited = PatientAssignment.objects.get(pk=assignment_id)
                        # Remove the current patient from the list of assigned IDs to exclude
                        if assignment_being_edited.patient_id in assigned_patient_ids:
                            assigned_patient_ids.remove(assignment_being_edited.patient_id)
                    except PatientAssignment.DoesNotExist:
                        pass # Should not happen, but good to be safe
            
            # Exclude all other assigned patients from the search results
            queryset = queryset.exclude(id__in=assigned_patient_ids)

        return queryset, use_distinct

# ------------------------------
# FoodItem Admin
# ------------------------------
@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = (
        "name", "calories", "protein", "carbs", "fats",
        "fodmap_level", "spice_level", "purine_level", "is_verified"
    )
    list_filter = ("fodmap_level", "spice_level", "purine_level", "is_verified")
    search_fields = ("name",)
    filter_horizontal = ("food_types", "meal_types", "allergens")

# ------------------------------
# Patient Assignment Admin
# ------------------------------
@admin.register(PatientAssignment)
class PatientAssignmentAdmin(admin.ModelAdmin):
    """
    Custom admin view for Patient Assignments.
    The filtering logic is now correctly placed in CustomUserAdmin.
    """
    list_display = ('patient', 'nutritionist', 'assigned_at')
    search_fields = ('patient__full_name', 'patient__email', 'nutritionist__full_name')
    list_filter = ('nutritionist', 'assigned_at')
    autocomplete_fields = ['patient', 'nutritionist']

    fieldsets = (
        (None, {
            'fields': ('patient', 'nutritionist', 'assigned_at')
        }),
    )
    
    # NOTE: The get_search_results method is NOT needed here. It is now in CustomUserAdmin.

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.nutritionist_id:
            if request.user.groups.filter(name='Nutritionist').exists():
                obj.nutritionist = request.user
        super().save_model(request, obj, form, change)


# ------------------------------
# Register Models with Admin
# ------------------------------
admin.site.register(User, CustomUserAdmin) # This now contains the filtering logic
admin.site.register(UserProfile)
admin.site.register(LabReport)
admin.site.register(UserMeal)
admin.site.register(CustomReminder)
admin.site.register(NutritionistProfile)
admin.site.register(DietRecommendation)
admin.site.register(Blog)
admin.site.register(Message)
admin.site.register(WeightLog)
admin.site.register(WaterIntakeLog)