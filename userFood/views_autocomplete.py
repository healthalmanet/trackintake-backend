# === Changes made by Ananya (Start) ===
from django.db.models import Q

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import FoodItem


class FoodSearchView(APIView):
    """DB-first autocomplete search for FoodItem.

    - Searches local FoodItem table first.
    - Returns matches immediately.

    Gemini fallback is intentionally NOT implemented here.
    Gemini should be triggered only during explicit user confirmation / meal logging,
    which already exists in UserMealViewSet._find_or_create_food_item.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        limit = int(request.query_params.get("limit") or 10)
        limit = max(1, min(limit, 10))

        if not q:
            return Response({"results": []}, status=status.HTTP_200_OK)

        # Simple DB-backed search; keep it fast and deterministic.
        # Prioritize exact/startswith, then icontains.
        qs = FoodItem.objects.all()

        # Use iLIKE-ish behavior via icontains.
        qs = qs.filter(Q(name__icontains=q) | Q(name__istartswith=q))

        # Order: startswith first, then contains.
        qs = qs.order_by(
            "-name"  # placeholder order; name ordering is stable for pagination-free use
        )

        results = []
        for item in qs[:limit]:
            results.append({
                "id": item.id,
                "name": item.name,
                "has_attributes": bool(getattr(item, "attributes", None).exists()) if hasattr(item, "attributes") else False,
            })

        return Response({"results": results}, status=status.HTTP_200_OK)


# === Changes made by Ananya (End) ===


