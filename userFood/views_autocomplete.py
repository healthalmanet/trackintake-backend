from django.db.models import Q, Case, When, Value, IntegerField
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import FoodItem, normalize_food_name


class FoodSearchView(APIView):
    """DB-first autocomplete search for FoodItem.

    Prioritizes:
      1. Exact normalized match on name_key
      2. Starts-with match on name
      3. Contains match on name

    Returns serving hints (gram_equivalent, calories_per_serving, default_unit)
    so the frontend can show "1 Bowl = 300g | ~390 kcal" before logging.

    Gemini is NOT triggered here — only during meal logging.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        q     = (request.query_params.get("q") or "").strip()
        limit = int(request.query_params.get("limit") or 10)
        limit = max(1, min(limit, 20))

        if not q:
            return Response({"results": []}, status=status.HTTP_200_OK)

        key = normalize_food_name(q)   # e.g. "white rice"

        # Priority ordering: exact name__iexact → startswith name → contains name
        # Only return valid food items with real nutrition (calories > 0 and gram_equivalent > 0)
        qs = FoodItem.objects.filter(
            Q(name__iexact=key) |
            Q(name__istartswith=q) |
            Q(name__icontains=q)
        ).filter(calories__gt=0, gram_equivalent__gt=0).annotate(
            match_rank=Case(
                When(name__iexact=key,        then=Value(0)),
                When(name__istartswith=q,     then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            )
        ).order_by('match_rank', 'name')

        results = []
        for item in qs[:limit]:
            gram_eq  = item.gram_equivalent or 0
            calories = item.calories or 0

            # Build a human-readable serving hint
            if item.default_unit and item.default_quantity:
                qty_label = f"{int(item.default_quantity) if item.default_quantity == int(item.default_quantity) else item.default_quantity}"
                serving_hint = f"{qty_label} {item.default_unit}"
                if gram_eq > 0:
                    unit_lower = (item.default_unit or "").lower()
                    metric_unit = "ml" if any(l in unit_lower for l in ["glass", "cup", "ml", "liquid", "liter"]) else "g"
                    serving_hint += f" = {int(gram_eq)}{metric_unit}"
                if calories > 0:
                    serving_hint += f" | ~{int(calories)} kcal"
            else:
                serving_hint = f"~{int(calories)} kcal" if calories > 0 else ""

            results.append({
                "id":                 item.id,
                "name":               item.name,
                "default_quantity":   item.default_quantity,
                "default_unit":       item.default_unit,
                "gram_equivalent":    gram_eq or None,
                "calories_per_serving": calories or None,
                "serving_hint":       serving_hint,
            })

        return Response({"results": results}, status=status.HTTP_200_OK)
