from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import DietRecommendation
User = get_user_model()

# class DietRecommendationSerializer(serializers.ModelSerializer):
#     user_full_name = serializers.CharField(source='user.full_name', read_only=True)
#     reviewer_full_name = serializers.CharField(source='reviewed_by.full_name', read_only=True)
#     class Meta:
#         model = DietRecommendation
#         fields = [
#             'id',
#             'user',
#             'user_full_name',
#             'for_week_starting',
#             'meals',
#             'status',
#             'nutritionist_comment',
#             'reviewed_by',
#             'reviewer_full_name',
#             # 'user_profile_snapshot',
#             # 'original_ai_plan',
#             # 'approved_for_retraining',
#             # 'nutritionist_retraining_notes',
#             # 'was_used_for_retraining',
#             'created_at',
#             'updated_at',
#         ]



class DietRecommendationSerializer(serializers.ModelSerializer):
    """
    DEFINITIVE VERSION: This serializer is engineered to produce the exact JSON
    output format of your original serializer for 100% backward compatibility.
    """
    
    # This field fetches the `full_name` from the related `user` object.
    # `source='user.full_name'` tells Django REST Framework to follow the relationship.
    # `read_only=True` means this field is for output only.
    user_full_name = serializers.CharField(source='user.full_name', read_only=True)
    
    # This does the same for the `reviewed_by` field.
    # We add `allow_null=True` as a safety measure, since `reviewed_by` can be null.
    reviewer_full_name = serializers.CharField(source='reviewed_by.full_name', read_only=True, allow_null=True)

    class Meta:
        model = DietRecommendation
        
        # This list of fields is taken directly from your original serializer
        # to ensure the output contains the exact same data in the same order.
        fields = [
            'id',
            'user', # This will be the user's ID
            'user_full_name',
            'for_week_starting',
            'meals',
            'status',
            'nutritionist_comment',
            'reviewed_by', # This will be the nutritionist's ID
            'reviewer_full_name',
            'created_at',
            'updated_at',
        ]