from datetime import date, timedelta, datetime, time
from django.utils import timezone
from django.utils.timezone import now
from django.utils.dateparse import parse_date
from django.db import transaction
from django.contrib.postgres.search import TrigramSimilarity
from dateutil import parser
import traceback
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, filters
from django.core.exceptions import ValidationError
from dateutil import parser
from fuzzywuzzy import process
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import api_view, permission_classes
from django.utils.timezone import make_aware



from utils.pagination import StandardResultsSetPagination
from utils.gemini import fetch_nutrition_from_gemini
from utils.utils import get_target_nutrients, send_email_notification_CALORIE, send_sms_notification

from .serializers import UserMealSerializer

from .models import UserMeal, FoodItem, Allergen, FoodType, MealType
from userProfile.models import UserProfile



# FUZZY_MATCH_THRESHOLD = 90

# class UserMealViewSet(viewsets.ModelViewSet):
#     serializer_class = UserMealSerializer
#     permission_classes = [IsAuthenticated]
#     pagination_class = StandardResultsSetPagination
#     filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
#     ordering_fields = ['consumed_at']
#     ordering = ['-consumed_at']
#     filterset_fields = ['date', 'meal_type']

#     def get_queryset(self):
        
#         return UserMeal.objects.filter(user=self.request.user).order_by('-consumed_at')

#     def create(self, request, *args, **kwargs):
#         def process_meal(item_data):
#             food_name = item_data.get("food_name", "").strip().lower()
#             if not food_name:
#                 raise ValueError("`food_name` cannot be empty.")

#             quantity = float(item_data.get("quantity", 1))
#             unit = item_data.get("unit", "g")
#             meal_type = item_data.get("meal_type", "breakfast")
#             remarks = item_data.get("remarks", "")
#             consumed_at_str = item_data.get("consumed_at")
#             date_str = item_data.get("date")

#             try:
#                 consumed_at = parser.parse(consumed_at_str) if consumed_at_str else timezone.now()
#                 date = parser.parse(date_str).date() if date_str else consumed_at.date()
#             except Exception as e:
#                 raise ValueError(f"Invalid date/time format: {e}")

#             food = FoodItem.objects.filter(name__iexact=food_name).first()
#             if not food:
#                 all_names = list(FoodItem.objects.values_list("name", flat=True))
#                 if all_names:
#                     match_result = process.extractOne(food_name, all_names)
#                     if match_result and match_result[1] >= FUZZY_MATCH_THRESHOLD:
#                         food = FoodItem.objects.get(name=match_result[0])

#             if not food:
#                 try:
#                     print(f"Food '{food_name}' not found. Querying Gemini...")
#                     gemini_data = fetch_nutrition_from_gemini(food_name, quantity, unit)
#                     food = FoodItem.objects.create(**gemini_data)
#                     print(f"Created new food item '{food.name}' via Gemini.")
#                 except Exception as e:
#                     raise ValueError(f"AI nutrition lookup failed for '{food_name}': {e}")

#             return UserMeal.objects.create(
#                 user=request.user,
#                 food_item=food,
#                 food_name=food.name,
#                 quantity=quantity,
#                 unit=unit,
#                 meal_type=meal_type,
#                 remarks=remarks,
#                 calories=food.calories,
#                 protein=food.protein,
#                 carbs=food.carbs,
#                 fats=food.fats,
#                 sugar=food.sugar,
#                 fiber=food.fiber,
#                 estimated_gi=food.estimated_gi,
#                 glycemic_load=food.glycemic_load,
#                 food_type=food.food_type,
#                 consumed_at=consumed_at,
#                 date=date
#             )

#         try:
#             payload = request.data
#             meals = [process_meal(item) for item in payload] if isinstance(payload, list) else [process_meal(payload)]
#             serializer = self.get_serializer(meals, many=True)

#             target_date = meals[0].date
#             start_of_day = make_aware(datetime.combine(target_date, time.min))
#             end_of_day = make_aware(datetime.combine(target_date, time.max))

#             totals = UserMeal.objects.filter(
#                 user=request.user,
#                 consumed_at__range=(start_of_day, end_of_day)
#             ).aggregate(
#                 total_calories=Sum('calories'),
#                 total_protein=Sum('protein'),
#                 total_carbs=Sum('carbs'),
#                 total_fats=Sum('fats'),
#                 total_sugar=Sum('sugar'),
#                 total_fiber=Sum('fiber'),
#             )
#             totals = {k: float(v) if v else 0 for k, v in totals.items()}

#             target_data = get_target_nutrients(request.user)
#             recommended_calories = target_data.get("recommended_calories", 0)

#             messages = []
#             if totals["total_calories"] >= recommended_calories:
#                 messages.append("✅ You've reached your daily calorie target!")
    

#             if messages and request.user.email:
#                 send_email_notification_CALORIE(
#                     request.user.email,
#                     "🎉 Nutrition Target Met!",
#                     "\n".join(messages),
#                     totals["total_calories"],
#                     recommended_calories,
#                     str(target_date)
#                 )

#             return Response({
#                 "message": "Meal logged successfully.",
#                 "notifications": messages,
#                 "totals": totals,
#                 "data": serializer.data
#             }, status=status.HTTP_201_CREATED)

#         except ValueError as e:
#             return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

#         except Exception as e:
#             import traceback
#             traceback.print_exc()
#             return Response({
#                 "error": "An unexpected error occurred while logging meals.",
#                 "details": str(e)
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     def partial_update(self, request, *args, **kwargs):
#         instance = self.get_object()
#         data = request.data

#         food_name = data.get("food_name", "").strip().lower()

#         if food_name:
#             food = FoodItem.objects.filter(name__iexact=food_name).first()
#             if not food:
#                 all_names = list(FoodItem.objects.values_list("name", flat=True))
#                 if all_names:
#                     match_result = process.extractOne(food_name, all_names)
#                     if match_result and match_result[1] >= FUZZY_MATCH_THRESHOLD:
#                         food = FoodItem.objects.get(name=match_result[0])

#             if not food:
#                 try:
#                     print(f"PATCH: Food '{food_name}' not found. Querying Gemini...")
#                     gemini_data = fetch_nutrition_from_gemini(food_name)
#                     food = FoodItem.objects.create(**gemini_data)
#                     print(f"Created new food '{food.name}' via Gemini in PATCH.")
#                 except Exception as e:
#                     return Response({"error": f"AI lookup failed: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

#             instance.food_item = food
#             instance.food_name = food.name

#         if "quantity" in data:
#             instance.quantity = float(data["quantity"])

#         instance.unit = data.get("unit", instance.unit)
#         instance.meal_type = data.get("meal_type", instance.meal_type)
#         instance.remarks = data.get("remarks", instance.remarks)

#         # ✅ Recalculate ALL nutrition proportionally
#         base_quantity = float(instance.food_item.gram_equivalent or 100)
#         factor = instance.quantity / base_quantity

#         def calc(value):
#             return round(value * factor, 2) if value is not None else 0

#         instance.calories = calc(instance.food_item.calories)
#         instance.protein = calc(instance.food_item.protein)
#         instance.carbs = calc(instance.food_item.carbs)
#         instance.fats = calc(instance.food_item.fats)
#         instance.sugar = calc(instance.food_item.sugar)
#         instance.fiber = calc(instance.food_item.fiber)
#         instance.saturated_fat_g = calc(instance.food_item.saturated_fat_g)
#         instance.trans_fat_g = calc(instance.food_item.trans_fat_g)
#         instance.estimated_gi = instance.food_item.estimated_gi
#         instance.glycemic_load = calc(instance.food_item.glycemic_load)
#         instance.sodium_mg = calc(instance.food_item.sodium_mg)
#         instance.potassium_mg = calc(instance.food_item.potassium_mg)
#         instance.iron_mg = calc(instance.food_item.iron_mg)
#         instance.calcium_mg = calc(instance.food_item.calcium_mg)
#         instance.iodine_mcg = calc(instance.food_item.iodine_mcg)
#         instance.zinc_mg = calc(instance.food_item.zinc_mg)
#         instance.magnesium_mg = calc(instance.food_item.magnesium_mg)
#         instance.selenium_mcg = calc(instance.food_item.selenium_mcg)
#         instance.cholesterol_mg = calc(instance.food_item.cholesterol_mg)
#         instance.omega_3_g = calc(instance.food_item.omega_3_g)
#         instance.vitamin_d_mcg = calc(instance.food_item.vitamin_d_mcg)
#         instance.vitamin_b12_mcg = calc(instance.food_item.vitamin_b12_mcg)
#         instance.food_type = instance.food_item.food_type

#         instance.save()

#         serializer = self.get_serializer(instance)
#         return Response({
#             "message": "Meal updated successfully.",
#             "data": serializer.data
#         }, status=status.HTTP_200_OK)





FUZZY_MATCH_THRESHOLD = 0.9


class UserMealViewSet(viewsets.ModelViewSet):
    serializer_class = UserMealSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['consumed_at']
    ordering = ['-consumed_at']
    filterset_fields = ['date', 'meal_type']

    def get_queryset(self):
        return UserMeal.objects.filter(user=self.request.user).order_by('-consumed_at')

    # --- THIS IS THE FIXED FUNCTION ---
# --- THIS IS THE UPDATED FUNCTION ---
    def _find_or_create_food_item(self, food_name: str, quantity: float, unit: str) -> 'FoodItem':
        """
        Finds a food item in the local database or creates a new one using Gemini.
        This version standardizes food names by always using the name provided by Gemini.
        """
        original_food_name = food_name.strip()
        if not original_food_name:
            raise ValueError("`food_name` cannot be empty.")

        # 1. Exact match (fastest and most accurate)
        food = FoodItem.objects.filter(name__iexact=original_food_name).first()
        if food:
            return food

        # 2. Conditional Fuzzy Match
        if len(original_food_name.split()) > 1:
            food = FoodItem.objects.annotate(
                similarity=TrigramSimilarity('name', original_food_name)
            ).filter(similarity__gt=FUZZY_MATCH_THRESHOLD).order_by('-similarity').first()
            if food:
                return food

        # 3. Gemini fallback to get a standardized food item
        print(f"🔄 Fallback: Querying Gemini API for a profile of '{original_food_name}'...")
        
        # This function call returns the saved FoodItem object from Gemini
        gemini_food_item = fetch_nutrition_from_gemini(original_food_name, quantity, unit)

        if not gemini_food_item:
            raise ValueError(f"Could not find nutrition info for '{original_food_name}'")

        # THE CHANGE IS HERE: We no longer check or swap names. We simply trust
        # and return the standardized food item that Gemini provided.
        print(f"✅ Standardized name via Gemini: User typed '{original_food_name}', using '{gemini_food_item.name}'.")
        
        return gemini_food_item

    def create(self, request, *args, **kwargs):
        def process_meal(item_data):
            food_name = item_data.get("food_name", "").strip()
            if not food_name:
                raise ValueError("`food_name` cannot be empty.")

            quantity = float(item_data.get("quantity", 1))
            unit = item_data.get("unit", "g")
            
            food = self._find_or_create_food_item(food_name, quantity, unit)

            consumed_at_str = item_data.get("consumed_at")
            date_str = item_data.get("date")
            try:
                consumed_at = parser.parse(consumed_at_str) if consumed_at_str else timezone.now()
                date = parser.parse(date_str).date() if date_str else consumed_at.date()
            except Exception as e:
                raise ValueError(f"Invalid date/time format: {e}")
            
            meal = UserMeal(
                user=request.user, food_item=food,
                quantity=quantity, unit=unit,
                meal_type=item_data.get("meal_type", "breakfast"),
                remarks=item_data.get("remarks", ""),
                consumed_at=consumed_at, date=date
            )
            meal.save()
            return meal

        try:
            payload = request.data
            with transaction.atomic():
                meals = [process_meal(item) for item in payload] if isinstance(payload, list) else [process_meal(payload)]
            
            serializer = self.get_serializer(meals, many=True)
            if not meals:
                return Response({"message": "No meals to log."}, status=status.HTTP_400_BAD_REQUEST)

            target_date = meals[0].date
            start_of_day = make_aware(datetime.combine(target_date, time.min))
            end_of_day = make_aware(datetime.combine(target_date, time.max))
            totals = UserMeal.objects.filter(user=request.user, consumed_at__range=(start_of_day, end_of_day)).aggregate(
                total_calories=Sum('calories'), total_protein=Sum('protein'),
                total_carbs=Sum('carbs'), total_fats=Sum('fats'),
                total_sugar=Sum('sugar'), total_fiber=Sum('fiber'),
            )
            totals = {k: float(v) if v is not None else 0 for k, v in totals.items()}
            target_data = get_target_nutrients(request.user)
            recommended_calories = target_data.get("recommended_calories", 0)
            messages = []
            if totals.get("total_calories", 0) >= recommended_calories:
                messages.append("✅ You've reached your daily calorie target!")
            if messages and request.user.email:
                send_email_notification_CALORIE(
                    request.user.email, "🎉 Nutrition Target Met!", "\n".join(messages),
                    totals.get("total_calories", 0), recommended_calories, str(target_date)
                )

            return Response({
                "message": "Meal logged successfully.", "notifications": messages,
                "totals": totals, "data": serializer.data
            }, status=status.HTTP_201_CREATED)

        except (ValueError, ValidationError) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            traceback.print_exc()
            return Response({"error": "An unexpected error occurred while logging meals."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        data = request.data
        try:
            with transaction.atomic():
                if "food_name" in data and data["food_name"].strip().lower() != (instance.food_item.name or "").lower():
                    instance.food_item = self._find_or_create_food_item(
                        data["food_name"], float(data.get("quantity", instance.quantity)), data.get("unit", instance.unit)
                    )
                
                instance.quantity = float(data.get("quantity", instance.quantity))
                instance.unit = data.get("unit", instance.unit)
                instance.meal_type = data.get("meal_type", instance.meal_type)
                instance.remarks = data.get("remarks", instance.remarks)
                
                if "consumed_at" in data: instance.consumed_at = parser.parse(data["consumed_at"])
                if "date" in data: instance.date = parser.parse(data["date"]).date()

                instance.save()

            serializer = self.get_serializer(instance)
            return Response({
                "message": "Meal updated successfully.", "data": serializer.data
            }, status=status.HTTP_200_OK)
        except (ValueError, ValidationError) as e:
            return Response({"error": f"Update failed: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            traceback.print_exc()
            return Response({"error": "An unexpected error occurred during the update."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)








# RENAMED and REFACTORED for clarity and correct functionality 
#7day
class DailyUserMealSummaryView(APIView):
    """
    Provides a 7-day summary of meals, ending on a specific date provided by the user.
    This replaces DailyUserMealSummaryView to be more explicit and timezone-safe.
    It expects a query parameter like: /api/your-endpoint/?end_date=2023-10-27
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # The frontend provides the user's local "today" as the end_date.
        end_date_str = request.query_params.get('end_date')

        if not end_date_str:
            # If no date is provided, it's an error. The client must specify the date.
            return Response({"error": "An 'end_date' query parameter is required. Use YYYY-MM-DD format."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Parse the string from the client into a date object.
            end_date = parse_date(end_date_str)
            if not end_date: raise ValueError # parse_date returns None on failure

            # Calculate the start date for the 7-day range.
            start_date = end_date - timedelta(days=6)
            
            # Filter based on the user-specific date range.
            # Assumes your UserMeal model has a `date` field of type DateField.
            meals = UserMeal.objects.filter(user=request.user, date__range=(start_date, end_date))

        except (ValueError, TypeError):
            return Response({"error": "Invalid date format for 'end_date'. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)

        # The rest of the logic remains the same.
        summary = (
            meals.values('date')
            .annotate(
                calories=Sum('calories'),
                protein=Sum('protein'),
                carbs=Sum('carbs'),
                fats=Sum('fats')
            )
            .order_by('date')
        )

        # To ensure the frontend receives a full 7-day structure even if some days have no meals,
        # you can create a date map.
        date_map = {item['date']: item for item in summary}
        response_data = []
        for i in range(7):
            current_date = start_date + timedelta(days=i)
            day_data = date_map.get(current_date, {
                'date': current_date.isoformat(),
                'calories': 0,
                'protein': 0,
                'carbs': 0,
                'fats': 0
            })
            response_data.append(day_data)

        return Response(response_data)





@api_view(['GET'])
@permission_classes([IsAuthenticated])
def targetNutrients(request):
    """
    Get user-specific calorie, macronutrient, water, and weight targets.
    Accepts optional 'current_date' (YYYY-MM-DD) for accurate age calculation.
    """
    try:
        current_date_str = request.query_params.get('current_date')
        today = parse_date(current_date_str) if current_date_str else date.today()

        profile = UserProfile.objects.get(user=request.user)
        dob = profile.date_of_birth
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

        weight = profile.weight_kg
        height = profile.height_cm
        gender = profile.gender
        activity_level = profile.activity_level
        goal = profile.goal

        # ✅ BMR Calculation (Mifflin-St Jeor)
        bmr = 10 * weight + 6.25 * height - 5 * age + (5 if gender == "male" else -161)

        activity_multipliers = {
            "sedentary": 1.2,
            "light": 1.3,
            "lightly_active": 1.3,
            "moderate": 1.45,
            "active": 1.6,
            "very_active": 1.75
        }

        maintenance_calories = bmr * activity_multipliers.get(activity_level.lower(), 1.2)

        # ✅ Adjust calories based on goal
        if goal == "Gain Weight":
            recommended_calories = maintenance_calories * 1.15
            target_weight = weight + 5
        elif goal == "Lose Weight":
            recommended_calories = maintenance_calories * 0.8
            target_weight = weight - 5
        else:
            recommended_calories = maintenance_calories
            target_weight = weight

        recommended_calories = round(recommended_calories)

        # ✅ Macronutrients Breakdown based on recommended_calories
        protein_g = round(weight * 1.8)
        fats_g = round(weight * 0.8)

        protein_calories = protein_g * 4
        fats_calories = fats_g * 9
        carbs_calories = recommended_calories - (protein_calories + fats_calories)
        carbs_g = round(carbs_calories / 4) if carbs_calories > 0 else 0

        sugar_g = round((recommended_calories * 0.1) / 4)
        fiber_g = round((recommended_calories / 1000) * 14)

        # ✅ Water Intake Recommendation
        base_water_ml = weight * 35
        activity_water_bonus = {
            "sedentary": 0,
            "light": 250,
            "lightly_active": 250,
            "moderate": 500,
            "active": 750,
            "very_active": 1000
        }
        recommended_water_ml = base_water_ml + activity_water_bonus.get(activity_level.lower(), 0)

        return Response({
            "bmr": round(bmr),
            "maintenance_calories": round(maintenance_calories),
            "recommended_calories": recommended_calories,
            "macronutrients": {
                "protein_g": protein_g,
                "carbs_g": carbs_g,
                "fats_g": fats_g,
                "sugar_g": sugar_g,
                "fiber_g": fiber_g
            },
            "water": {
                "recommended_ml": round(recommended_water_ml)
            },
            "weight_target": {
                "current_weight_kg": round(weight, 1),
                "target_weight_kg": round(target_weight, 1),
                "goal": goal
            },
            "activity_level": activity_level
        })

    except UserProfile.DoesNotExist:
        return Response({"error": "User profile not found."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class targetNutrientsUpdate(APIView):
    """
    Provides a total summary for a single day.
    This view MUST receive a 'date' parameter from the client to avoid timezone issues.
    Example: /api/daily-summary/?date=2023-10-27
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get the target date string from the query parameters.
        date_str = request.query_params.get('date')

        if not date_str:
            return Response({"error": "A 'date' query parameter is required. Use YYYY-MM-DD format."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # This is the user's local date, parsed into a date object.
            target_date = parse_date(date_str)
            if not target_date: raise ValueError()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)

        # Create a timezone-aware datetime range for the user's entire local day.
        # This assumes UserMeal.consumed_at is a timezone-aware DateTimeField.
        start_of_day = datetime.combine(target_date, time.min)
        end_of_day = datetime.combine(target_date, time.max)

        # If your project uses timezones (settings.USE_TZ=True), you should make these
        # datetimes aware of the current timezone to match the database.
        # from django.utils.timezone import make_aware
        # start_of_day = make_aware(datetime.combine(target_date, time.min))
        # end_of_day = make_aware(datetime.combine(target_date, time.max))
        
        # The filter now correctly queries for meals within the user's local day.
        meals_today = UserMeal.objects.filter(
            user=request.user, 
            consumed_at__gte=start_of_day, 
            consumed_at__lte=end_of_day
        )

        totals = meals_today.aggregate(
            total_calories=Sum("calories", default=0),
            total_protein=Sum("protein", default=0),
            total_carbs=Sum("carbs", default=0),
            total_fats=Sum("fats", default=0),
            total_sugar=Sum("sugar", default=0),
            total_fiber=Sum("fiber", default=0),
        )

        return Response({
            "date": target_date,
            "calories": totals["total_calories"],
            "protein": totals["total_protein"],
            "carbs": totals["total_carbs"],
            "fats": totals["total_fats"],
            "sugar": totals["total_sugar"],
            "fiber": totals["total_fiber"],
        })