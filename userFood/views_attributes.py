"""
Food Attributes API Views

This module provides REST API endpoints for the food attributes system.
These endpoints allow the frontend to:
1. Fetch attributes for a specific food
2. Fetch available options for each attribute
3. Handle food attributes in meal logging
"""

from rest_framework import viewsets, status, generics
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db import transaction

from .models import (
    FoodItem, FoodAttribute, FoodAttributeOption,
    FoodItemAttribute, UserMeal, UserMealAttribute
)
from .serializers import (
    FoodAttributeSerializer, FoodAttributeOptionSerializer,
    FoodItemWithAttributesSerializer, UserMealWithAttributesSerializer,
    UserMealAttributeSerializer
)


class FoodAttributesDetailView(APIView):
    """
    GET /userFood/foods/{food_id}/attributes/

    Fetch all attributes and their options for a specific food item.
    This endpoint should be called AFTER the user selects a food,
    to show them what additional information they need to provide.

    Response format:
    {
        "food_id": 1,
        "food_name": "Chapati",
        "attributes": [
            {
                "id": 1,
                "name": "Flour Type",
                "description": "Type of flour used",
                "options": [
                    {"id": 1, "value": "Wheat", "display_name": "Whole Wheat", "nutrition_multiplier": 1.0},
                    {"id": 2, "value": "Bajra", "display_name": "Pearl Millet", "nutrition_multiplier": 1.05},
                    ...
                ]
            },
            {
                "id": 2,
                "name": "Size",
                "description": "Size of the chapati",
                "options": [
                    {"id": 10, "value": "Small", "display_name": "Small", "nutrition_multiplier": 0.8},
                    {"id": 11, "value": "Medium", "display_name": "Medium", "nutrition_multiplier": 1.0},
                    {"id": 12, "value": "Large", "display_name": "Large", "nutrition_multiplier": 1.3},
                ]
            }
        ]
    }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, food_id):
        """Get attributes for a specific food item."""
        try:
            food_item = FoodItem.objects.get(id=food_id)
        except FoodItem.DoesNotExist:
            return Response(
                {"error": f"Food item with id {food_id} not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get all food-attribute relationships for this food
        food_attributes = FoodItemAttribute.objects.filter(
            food_item=food_item,
            attribute__is_active=True
        ).select_related('attribute')

        # Serialize the attributes with their options
        attributes_data = []
        for fa in food_attributes:
            attribute_data = {
                "id": fa.attribute.id,
                "name": fa.attribute.name,
                "description": fa.attribute.description or "",
                "is_required": fa.is_required,
                "options": FoodAttributeOptionSerializer(
                    fa.attribute.options.filter(is_active=True),
                    many=True
                ).data
            }
            attributes_data.append(attribute_data)

        return Response({
            "food_id": food_item.id,
            "food_name": food_item.name,
            "attributes": attributes_data,
            "has_attributes": len(attributes_data) > 0
        })


class AttributeOptionsView(APIView):
    """
    GET /userFood/attributes/{attribute_id}/options/

    Fetch all available options for a specific attribute.
    Useful for dynamic dropdowns or filters in the frontend.

    Response format:
    {
        "attribute_id": 1,
        "attribute_name": "Flour Type",
        "options": [
            {"id": 1, "value": "Wheat", "display_name": "Whole Wheat", "nutrition_multiplier": 1.0},
            {"id": 2, "value": "Bajra", "display_name": "Pearl Millet", "nutrition_multiplier": 1.05},
            ...
        ]
    }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, attribute_id):
        """Get options for a specific attribute."""
        try:
            attribute = FoodAttribute.objects.get(
                id=attribute_id, is_active=True)
        except FoodAttribute.DoesNotExist:
            return Response(
                {"error": f"Attribute with id {attribute_id} not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        options = attribute.options.filter(is_active=True).order_by('value')

        return Response({
            "attribute_id": attribute.id,
            "attribute_name": attribute.name,
            "description": attribute.description or "",
            "options": FoodAttributeOptionSerializer(options, many=True).data
        })


class MealAttributesView(APIView):
    """
    POST /userFood/meals/{meal_id}/attributes/
    GET  /userFood/meals/{meal_id}/attributes/

    Manage attribute values for a specific meal.
    After creating a meal, the frontend should call this endpoint
    to associate attribute values with that meal.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, meal_id):
        """Get attributes that were selected for a specific meal."""
        try:
            meal = UserMeal.objects.get(id=meal_id, user=request.user)
        except UserMeal.DoesNotExist:
            return Response(
                {"error": f"Meal with id {meal_id} not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        meal_attributes = UserMealAttribute.objects.filter(user_meal=meal)
        serializer = UserMealAttributeSerializer(meal_attributes, many=True)

        return Response({
            "meal_id": meal.id,
            "food_name": meal.food_name,
            "attributes": serializer.data
        })

    @transaction.atomic
    def post(self, request, meal_id):
        """
        Save attribute values for a meal.

        Request body format:
        {
            "attributes": [
                {
                    "attribute_id": 1,
                    "option_id": 2  # Selected option for this attribute
                },
                {
                    "attribute_id": 2,
                    "option_id": 11
                }
            ]
        }
        """
        try:
            meal = UserMeal.objects.get(id=meal_id, user=request.user)
        except UserMeal.DoesNotExist:
            return Response(
                {"error": f"Meal with id {meal_id} not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        attributes_data = request.data.get("attributes", [])
        if not attributes_data:
            return Response(
                {"error": "No attributes provided"},
                status=status.HTTP_400_BAD_REQUEST
            )

        created_attributes = []
        errors = []

        for attr_input in attributes_data:
            attribute_id = attr_input.get("attribute_id")
            option_id = attr_input.get("option_id")

            if not attribute_id or not option_id:
                errors.append({
                    "error": "Both attribute_id and option_id are required",
                    "input": attr_input
                })
                continue

            try:
                # Get the attribute and option
                attribute = FoodAttribute.objects.get(id=attribute_id)
                option = FoodAttributeOption.objects.get(
                    id=option_id,
                    attribute=attribute
                )

                # Create or update the meal attribute
                meal_attr, created = UserMealAttribute.objects.update_or_create(
                    user_meal=meal,
                    attribute=attribute,
                    defaults={"selected_option": option}
                )

                created_attributes.append({
                    "attribute_id": attribute.id,
                    "attribute_name": attribute.name,
                    "option_id": option.id,
                    "option_value": option.value,
                    "nutrition_multiplier": option.nutrition_multiplier,
                    "created": created
                })

            except FoodAttribute.DoesNotExist:
                errors.append({
                    "error": f"Attribute {attribute_id} not found",
                    "attribute_id": attribute_id
                })
            except FoodAttributeOption.DoesNotExist:
                errors.append({
                    "error": f"Option {option_id} not found for attribute {attribute_id}",
                    "option_id": option_id,
                    "attribute_id": attribute_id
                })

        if errors and not created_attributes:
            return Response({
                "error": "Failed to save attributes",
                "details": errors
            }, status=status.HTTP_400_BAD_REQUEST)

        # IMPORTANT: attributes affect nutrition snapshot. Recalculate after saving.
        # Ensure we persist all nutrition snapshot fields (including estimated_gi).
        try:
            meal.refresh_from_db(fields=['quantity', 'unit', 'portion_size', 'food_item', 'food_name', 'consumed_at', 'date'])
            meal._calculate_and_set_nutrients()
            meal.save(update_fields=[
                'calories',
                'protein',
                'carbs',
                'fats',
                'sugar',
                'fiber',
                'estimated_gi',
                'glycemic_load',
                'food_type',
            ])
        except Exception:
            # Defensive: attributes persistence should still succeed even if calc fails.
            logger.exception("Failed to recalculate meal nutrition after attribute save")


        return Response({
            "meal_id": meal.id,
            "food_name": meal.food_name,
            "created_attributes": created_attributes,
            "errors": errors if errors else None
        }, status=status.HTTP_201_CREATED if not errors else status.HTTP_207_MULTI_STATUS)



class FoodWithAttributesView(generics.RetrieveAPIView):
    """
    GET /userFood/foods/{id}/

    Get food item details WITH attributes.
    This is the main endpoint for fetching food details.
    """
    queryset = FoodItem.objects.all()
    serializer_class = FoodItemWithAttributesSerializer
    permission_classes = [IsAuthenticated]


class FoodWithAttributesByNameView(APIView):
    """
    GET /userFood/foods/by-name/{name}/

    Case-insensitive lookup of a FoodItem by name.

    Returns the FoodItem details INCLUDING its required/available attributes,
    reusing FoodItemWithAttributesSerializer.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, name: str):
        # Production-safe: trim whitespace and use case-insensitive lookup.
        name = (name or "").strip()
        food_item = FoodItem.objects.filter(name__iexact=name).first()

        if not food_item:
            return Response(
                {"error": f"Food item with name '{name}' not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = FoodItemWithAttributesSerializer(food_item)
        return Response(serializer.data, status=status.HTTP_200_OK)



class MealWithAttributesViewSet(viewsets.ViewSet):
    """
    GET    /userFood/logmeals_with_attributes/
    POST   /userFood/logmeals_with_attributes/
    GET    /userFood/logmeals_with_attributes/{id}/
    PATCH  /userFood/logmeals_with_attributes/{id}/
    DELETE /userFood/logmeals_with_attributes/{id}/

    This is an ALTERNATIVE endpoint for logging meals that also handles attributes.
    The traditional /logmeals/ endpoint continues to work as before (backward compatible).

    Use this new endpoint if you want to log a meal AND its attributes in a combined workflow.
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """List meals with their attributes."""
        meals = UserMeal.objects.filter(
            user=request.user).order_by('-consumed_at')
        serializer = UserMealWithAttributesSerializer(meals, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """Get a specific meal with its attributes."""
        try:
            meal = UserMeal.objects.get(id=pk, user=request.user)
            serializer = UserMealWithAttributesSerializer(meal)
            return Response(serializer.data)
        except UserMeal.DoesNotExist:
            return Response(
                {"error": "Meal not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    def create(self, request):
        """
        Create a meal with attributes.

        Request body format:
        {
            "food_name": "Chapati",
            "quantity": 2,
            "unit": "Piece",
            "meal_type": "Lunch",
            "portion_size": "Medium",
            "attributes": [
                {
                    "attribute_id": 1,
                    "option_id": 2
                },
                {
                    "attribute_id": 2,
                    "option_id": 11
                }
            ]
        }
        """
        # Import here to avoid circular imports
        from userFood.views import UserMealViewSet

        # Extract attributes from the request
        attributes_data = request.data.pop("attributes", [])

        # Create the meal using the existing UserMealViewSet logic
        meal_viewset = UserMealViewSet()
        meal_viewset.request = request
        meal_viewset.format_kwarg = None

        # Create the meal first
        meal_response = meal_viewset.create(request)

        if meal_response.status_code not in [200, 201]:
            return meal_response

        # Extract meal ID from response (serializer response shapes vary)
        meal_data = meal_response.data if hasattr(meal_response, "data") else None
        meal_id = None

        # Production-safe extraction:
        # - UserMealViewSet.create() returns {"data": <ReturnList>} where ReturnList is list-like.
        # - In your traceback, this becomes: { "data": [ {"id": 82, ...} ] }
        if isinstance(meal_data, dict):
            data_field = meal_data.get("data")

            # Case 1: data_field is a list/ReturnList
            if isinstance(data_field, (list, tuple)):
                if data_field and isinstance(data_field[0], dict):
                    meal_id = data_field[0].get("id")

            # Case 2: data_field is a dict
            elif isinstance(data_field, dict):
                meal_id = data_field.get("id")

            # Final fallback: sometimes id is directly under meal_data
            if meal_id is None:
                meal_id = meal_data.get("id")

        # If meal_data itself is list-like (defensive)
        if meal_id is None and isinstance(meal_data, (list, tuple)):
            if meal_data and isinstance(meal_data[0], dict):
                meal_id = meal_data[0].get("id")





        if not meal_id:
            # Include response payload for easier debugging
            return Response(
                {
                    "error": "Failed to create meal",
                    "meal_response": meal_response.data,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


        # Now add the attributes if any were provided
        if attributes_data:
            # Reuse the attribute creation logic directly (no fake request mutation)
            attr_errors = []
            for attr_input in attributes_data:
                attribute_id = attr_input.get("attribute_id")
                option_id = attr_input.get("option_id")

                if not attribute_id or not option_id:
                    attr_errors.append({
                        "error": "Both attribute_id and option_id are required",
                        "input": attr_input
                    })
                    continue

                try:
                    attribute = FoodAttribute.objects.get(id=attribute_id)
                    option = FoodAttributeOption.objects.get(
                        id=option_id,
                        attribute=attribute
                    )

                    # Create or update the meal attribute
                    UserMealAttribute.objects.update_or_create(
                        user_meal_id=meal_id,
                        attribute_id=attribute_id,
                        defaults={"selected_option": option}
                    )

                except FoodAttribute.DoesNotExist:
                    attr_errors.append({
                        "error": f"Attribute {attribute_id} not found",
                        "attribute_id": attribute_id
                    })
                except FoodAttributeOption.DoesNotExist:
                    attr_errors.append({
                        "error": f"Option {option_id} not found for attribute {attribute_id}",
                        "option_id": option_id,
                        "attribute_id": attribute_id
                    })

            if attr_errors:
                return Response(
                    {
                        "meal_created": True,
                        "meal_id": meal_id,
                        "attributes_error": attr_errors,
                    },
                    status=status.HTTP_207_MULTI_STATUS,
                )


        return Response({
            "success": True,
            "meal_id": meal_id,
            "attributes_saved": len(attributes_data) > 0
        }, status=status.HTTP_201_CREATED)
