# userFood: Meal Logging Engine Documentation

See the root documentation for the full comprehensive specification:
👉 [Root LOG_MEALS_README.md](../../LOG_MEALS_README.md)

---

## Quick Reference Summary

1. **`FoodItem` is strictly immutable**: User meal logs and overrides never mutate rows in `FoodItem`.
2. **Proportional Calculation**:
   $$\text{factor} = \frac{\text{effective\_grams}}{\text{food\_item.gram\_equivalent}}$$
   $$\text{nutrient} = \text{round}(\text{food\_item.nutrient} \times \text{factor}, 2)$$
3. **Serving Weights (`SERVING_UNIT_TO_GRAMS`)**:
   - `Bowl`: 150g (Default project bowl)
   - `Small Bowl`: 100g
   - `Big Bowl`: 250g
   - `Plate`: 350g
   - `Small Plate`: 200g
   - `Big Plate`: 500g
   - `Glass`: 250ml / 250g
   - `Katori`: 150g
   - `Thali`: 400g
4. **Exact Normalization**: `normalize_food_name(raw) = ' '.join(raw.strip().lower().split())`.
5. **No Attribute Tables**: `FoodAttribute`, `FoodAttributeOption`, `FoodItemAttribute`, and `UserMealAttribute` are deprecated and not part of the active logging UX.
