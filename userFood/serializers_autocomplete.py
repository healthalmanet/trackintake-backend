from rest_framework import serializers


class FoodAutocompleteResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    has_attributes = serializers.BooleanField()

