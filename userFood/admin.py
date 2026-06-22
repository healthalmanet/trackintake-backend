from django.contrib import admin
from .models import (
    FoodAttribute,
    FoodAttributeOption,
    FoodItemAttribute,
    UserMealAttribute,
)

admin.site.register(FoodAttribute)
admin.site.register(FoodAttributeOption)
admin.site.register(FoodItemAttribute)
admin.site.register(UserMealAttribute)
