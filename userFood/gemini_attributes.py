# === Changes made by Ananya (Start) ===
"""Helpers for creating AI-generated FoodAttribute/FoodAttributeOption/FoodItemAttribute.

Requirements satisfied:
- Keep attribute_matcher.py unchanged (known foods still use its mapping).
- Only create AI attributes when FoodItem has no existing attributes.
- Normalize names to avoid duplicates.
- Deduplicate FoodAttributeOption by (attribute, value).

Gemini should provide:
{
  "attributes": [
    {
      "name": "Size",
      "is_required": true,
      "options": [
        {"value": "Small", "display_name": "Small", "nutrition_multiplier": 1.0}
      ]
    }
  ]
}
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from django.db import transaction

from .models import FoodItem, FoodAttribute, FoodAttributeOption, FoodItemAttribute


def _norm(s: Optional[str]) -> str:
    return (s or "").strip()


def _norm_attr_name(name: str) -> str:
    # Keep it human readable but normalize duplicates.
    # Example: "flour type" -> "Flour Type"
    name = _norm(name)
    if not name:
        return name
    return " ".join([p[:1].upper() + p[1:].lower() if p else p for p in name.split()])


def _norm_option_value(val: str) -> str:
    return _norm(val)


@transaction.atomic
def apply_gemini_attributes_to_food_if_missing(food_item: FoodItem, gemini_payload: Dict[str, Any]) -> bool:
    """Apply AI-generated attributes iff the FoodItem has no attributes yet.

    Returns True if attributes were applied, else False.
    """
    if food_item is None:
        return False

    # If attribute_matcher already linked attributes, do not touch.
    # Note: related_name='attributes' exists on FoodItem.
    try:
        has_existing = food_item.attributes.exists()
    except Exception:
        # Defensive: if relation isn't present for some reason, treat as missing.
        has_existing = False

    if has_existing:
        return False

    attrs = gemini_payload.get("attributes") or []
    if not isinstance(attrs, list) or not attrs:
        return False

    for attr_obj in attrs:
        if not isinstance(attr_obj, dict):
            continue

        raw_attr_name = _norm_attr_name(attr_obj.get("name"))
        if not raw_attr_name:
            continue

        is_required = bool(attr_obj.get("is_required", True))
        options = attr_obj.get("options") or []
        if not isinstance(options, list) or not options:
            continue

        attr_record, _ = FoodAttribute.objects.get_or_create(
            name=raw_attr_name,
            defaults={
                "description": attr_obj.get("description") or "",
                "is_active": True,
            },
        )

        # Ensure FoodItemAttribute exists with required flag (dedupe by unique_together).
        FoodItemAttribute.objects.get_or_create(
            food_item=food_item,
            attribute=attr_record,
            defaults={
                "is_required": is_required,
                "order": 0,
            },
        )

        for opt in options:
            if not isinstance(opt, dict):
                continue
            value = _norm_option_value(opt.get("value"))
            if not value:
                continue

            display_name = opt.get("display_name") or value
            nutrition_multiplier = opt.get("nutrition_multiplier", 1.0)
            try:
                nutrition_multiplier = float(nutrition_multiplier)
            except Exception:
                nutrition_multiplier = 1.0

            opt_record, _ = FoodAttributeOption.objects.get_or_create(
                attribute=attr_record,
                value=value,
                defaults={
                    "display_name": display_name,
                    "description": opt.get("description") or "",
                    "nutrition_multiplier": nutrition_multiplier,
                    "is_active": True,
                },
            )

            # If it already existed, we still want to ensure nutrition_multiplier is not missing.
            if opt_record.nutrition_multiplier != nutrition_multiplier:
                opt_record.nutrition_multiplier = nutrition_multiplier
                opt_record.save(update_fields=["nutrition_multiplier"])

    return True


# === Changes made by Ananya (End) ===

