from rest_framework import serializers
from .models import UserProfile, LabReport

class UserProfileSerializer(serializers.ModelSerializer):
    age = serializers.IntegerField(read_only=True)
    bmi = serializers.FloatField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'date_of_birth', 'age', 'country', 'city', 'mobile_number', 'gender', 
            'height_cm', 'weight_kg', 'bmi',
            'occupation', 'activity_level', 'goal', 'diet_type', 'allergies',
            'is_diabetic', 'is_hypertensive', 'has_heart_condition', 
            'has_thyroid_disorder', 'has_arthritis', 'has_gastric_issues',
            'other_chronic_condition', 'family_history'
        ]

    def to_internal_value(self, data):
        if hasattr(data, 'copy'):
            mutable_data = data.copy()
        elif hasattr(data, 'dict'):
            mutable_data = data.dict()
        else:
            mutable_data = dict(data)

        if mutable_data.get('date_of_birth') in ['', 'null', 'None', 'undefined']:
            mutable_data['date_of_birth'] = None
        if mutable_data.get('height_cm') in ['', 'null', 'None', 'undefined', None]:
            mutable_data['height_cm'] = None
        if mutable_data.get('weight_kg') in ['', 'null', 'None', 'undefined', None]:
            mutable_data['weight_kg'] = None

        for b_field in [
            'is_diabetic', 'is_hypertensive', 'has_heart_condition',
            'has_thyroid_disorder', 'has_arthritis', 'has_gastric_issues'
        ]:
            if b_field in mutable_data:
                val = mutable_data[b_field]
                if isinstance(val, str):
                    mutable_data[b_field] = val.lower() in ('true', '1', 'yes')

        return super().to_internal_value(mutable_data)

class LabReportSerializer(serializers.ModelSerializer):
    """
    Serializer for creating, listing, and updating Lab Reports.
    """
    user = serializers.StringRelatedField(read_only=True) # Show user's name, but don't allow changing it
    report_file = serializers.FileField(required=False, allow_null=True)
    
    class Meta:
        model = LabReport
        fields = '__all__' # Include all fields from the model
        read_only_fields = ('user',) # The user is set automatically in the view

    def to_internal_value(self, data):
        if hasattr(data, 'copy'):
            mutable_data = data.copy()
        elif hasattr(data, 'dict'):
            mutable_data = data.dict()
        else:
            mutable_data = dict(data)

        if mutable_data.get('report_date') in ['', 'null', 'None', 'undefined', None]:
            mutable_data.pop('report_date', None)

        rf = mutable_data.get('report_file')
        if rf in ['', 'null', 'None', 'undefined', None] or isinstance(rf, str):
            mutable_data.pop('report_file', None)

        int_fields = ['blood_pressure_systolic', 'blood_pressure_diastolic']
        for int_f in int_fields:
            if int_f in mutable_data:
                val = mutable_data[int_f]
                if val in ['', 'null', 'None', 'undefined', None]:
                    mutable_data.pop(int_f, None)
                else:
                    try:
                        mutable_data[int_f] = int(round(float(val)))
                    except (ValueError, TypeError):
                        mutable_data.pop(int_f, None)

        num_fields = [
            'weight_kg', 'height_cm', 'waist_circumference_cm',
            'fasting_blood_sugar', 'postprandial_sugar', 'hba1c',
            'ldl_cholesterol', 'hdl_cholesterol', 'triglycerides', 'crp', 'esr',
            'uric_acid', 'creatinine', 'urea', 'alt', 'ast', 'vitamin_d3',
            'vitamin_b12', 'tsh'
        ]
        for nf in num_fields:
            if nf in mutable_data:
                val = mutable_data[nf]
                if val in ['', 'null', 'None', 'undefined', None]:
                    mutable_data.pop(nf, None)
                else:
                    try:
                        mutable_data[nf] = float(val)
                    except (ValueError, TypeError):
                        mutable_data.pop(nf, None)

        return super().to_internal_value(mutable_data)

