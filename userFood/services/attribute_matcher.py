from userFood.models import (
    FoodItem,
    FoodAttribute,
    FoodItemAttribute,
)

FOOD_LINKS = {
    'Chapati': [
        ('Flour Type', 1, True),
        ('Size', 2, True),
    ],
    'Roti': [
        ('Flour Type', 1, True),
        ('Size', 2, True),
    ],
    'Milk': [
        ('Fat Type', 1, True),
    ],
    'Rice': [
        ('Size', 1, False),
        ('Cooking Style', 2, False),
    ],
    'Tea': [
        ('Sugar Level', 1, True),
    ],
    'Pizza': [
        ('Size', 1, True),
        ('Crust Type', 2, True),
    ],
    'Burger': [
        ('Burger Type', 1, True),
        ('Burger Size', 2, True),
        ('Burger Add-ons', 3, False),
        ('Patty Count', 4, False),
    ],
    'Paratha': [
        ('Paratha Type', 1, True),
        ('Ghee Level', 2, False),
    ],
    'Dosa': [
        ('Dosa Type', 1, True),
    ],
    'Idli': [
        ('Idli Type', 1, True),
    ],
    'Momos': [
        ('Momos Type', 1, True),
        ('Preparation Type', 2, False),
    ],
    'Juice': [
        ('Juice Type', 1, True),
        ('Sugar Added', 2, False),
    ],
    'Ice Cream': [
        ('Ice Cream Type', 1, True),
    ],
}


def link_food_attributes(food_item):
    food_name = (
        food_item.name.lower()
        .replace(",", " ")
        .replace("-", " ")
        .strip()
    )

    matched = None

    for key in FOOD_LINKS.keys():
       normalized_key = key.lower().strip()

       if (
           normalized_key == food_name
           or food_name.startswith(normalized_key)
           or normalized_key in food_name.split()
           or normalized_key in food_name
        ):
           matched = key
           break

    if not matched:
        return

    for attr_name, order, required in FOOD_LINKS[matched]:

        try:
            attr = FoodAttribute.objects.get(name=attr_name)
        except FoodAttribute.DoesNotExist:
            continue

        FoodItemAttribute.objects.get_or_create(
            food_item=food_item,
            attribute=attr,
            defaults={
                "order": order,
                "is_required": required,
            }
        )
