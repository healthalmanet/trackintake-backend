from rest_framework import serializers
from .models import UserProfile, LabReport

class UserProfileSerializer(serializers.ModelSerializer):
    age = serializers.IntegerField(read_only=True)
    bmi = serializers.FloatField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'date_of_birth', 'age', 'country',"city", 'mobile_number', 'gender', 
            'height_cm', 'weight_kg', 'bmi',
            
            # --- ✅ ADD 'occupation' TO THIS LIST ---
            'occupation', 'activity_level', 'goal', 'diet_type', 'allergies',
            # --- END ADD ---
            
            'is_diabetic', 'is_hypertensive', 'has_heart_condition', 
            'has_thyroid_disorder', 'has_arthritis', 'has_gastric_issues',
            'other_chronic_condition', 'family_history'
        ]

class LabReportSerializer(serializers.ModelSerializer):
    """
    Serializer for creating, listing, and updating Lab Reports.
    """
    user = serializers.StringRelatedField(read_only=True) # Show user's name, but don't allow changing it
    
    class Meta:
        model = LabReport
        fields = '__all__' # Include all fields from the model
        read_only_fields = ('user',) # The user is set automatically in the view

