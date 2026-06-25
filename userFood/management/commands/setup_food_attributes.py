"""
Django management command to set up example food attributes.

Usage:
    python manage.py setup_food_attributes

This command creates example attributes and links them to existing foods.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from userFood.models import (
    FoodItem, FoodAttribute, FoodAttributeOption, FoodItemAttribute
)
from userFood.services.attribute_matcher import FOOD_LINKS


class Command(BaseCommand):
    help = 'Sets up example food attributes for Chapati, Milk, Rice, and Tea'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recreation of attributes even if they already exist',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        force = options.get('force', False)

        self.stdout.write(self.style.SUCCESS(
            '🚀 Setting up food attributes...'))

        # ========== SETUP ATTRIBUTES ==========
        attributes = {
            'Flour Type': {
                'description': 'Type of flour used in bread',
                'options': [
                    {'value': 'Wheat', 'display_name': 'Whole Wheat', 'multiplier': 1.0},
                    {'value': 'Bajra', 'display_name': 'Pearl Millet',
                        'multiplier': 1.05},
                    {'value': 'Jowar', 'display_name': 'Sorghum', 'multiplier': 1.02},
                    {'value': 'Multigrain', 'display_name': 'Multigrain',
                        'multiplier': 1.03},
                    {'value': 'Ragi', 'display_name': 'Finger Millet',
                        'multiplier': 1.08},
                ]
            },
            'Fat Type': {
                'description': 'Fat content level in dairy products',
                'options': [
                    {'value': 'Toned', 'display_name': 'Toned', 'multiplier': 0.95},
                    {'value': 'Double Toned',
                        'display_name': 'Double Toned', 'multiplier': 0.90},
                    {'value': 'Full Cream',
                        'display_name': 'Full Cream', 'multiplier': 1.0},
                    {'value': 'Skimmed', 'display_name': 'Skimmed', 'multiplier': 0.85},
                ]
            },
            'Size': {
                'description': 'Size of the food item',
                'options': [
                    {'value': 'Small', 'display_name': 'Small', 'multiplier': 0.8},
                    {'value': 'Medium', 'display_name': 'Medium', 'multiplier': 1.0},
                    {'value': 'Large', 'display_name': 'Large', 'multiplier': 1.3},
                    {'value': 'Extra Large',
                        'display_name': 'Extra Large', 'multiplier': 1.6},
                ]
            },
            'Sugar Level': {
                'description': 'Sugar content level in beverages',
                'options': [
                    {'value': 'No Sugar', 'display_name': 'No Sugar', 'multiplier': 0.8},
                    {'value': 'Low', 'display_name': 'Low', 'multiplier': 0.9},
                    {'value': 'Medium',
                        'display_name': 'Medium (Standard)', 'multiplier': 1.0},
                    {'value': 'High',
                        'display_name': 'High (Extra Sweet)', 'multiplier': 1.15},
                ]
            },
            'Crust Type': {
                'description': 'Type of crust for pizza',
                'options': [
                    {'value': 'Thin', 'display_name': 'Thin Crust', 'multiplier': 0.85},
                    {'value': 'Regular', 'display_name': 'Regular Crust',
                        'multiplier': 1.0},
                    {'value': 'Thick', 'display_name': 'Thick Crust', 'multiplier': 1.2},
                    {'value': 'Stuffed', 'display_name': 'Stuffed Crust',
                        'multiplier': 1.35},
                ]
            },
            'Pizza Size': {
                'description': 'Size of pizza',
                'options': [
                    {'value': 'Personal', 'display_name': 'Personal', 'multiplier': 0.7},
                    {'value': 'Small', 'display_name': 'Small', 'multiplier': 1.0},
                    {'value': 'Medium', 'display_name': 'Medium', 'multiplier': 1.5},
                    {'value': 'Large', 'display_name': 'Large', 'multiplier': 2.0},
                ]
            },
            'Cheese Option': {
                'description': 'Cheese preference',
                'options': [
                    {'value': 'No Cheese', 'display_name': 'No Cheese',
                        'multiplier': 1.0},
                    {'value': 'Regular Cheese',
                        'display_name': 'Regular Cheese', 'multiplier': 1.1},
                    {'value': 'Extra Cheese',
                        'display_name': 'Extra Cheese', 'multiplier': 1.2},
                ]
            },
            'Pizza Type': {
                'description': 'Type of pizza',
                'options': [
                    {
                        'value': 'Margherita',
                        'display_name': 'Margherita',
                        'multiplier': 1.0
                    },
                    {
                        'value': 'Farmhouse',
                        'display_name': 'Farmhouse',
                        'multiplier': 1.15
                    },
                    {
                        'value': 'Paneer',
                        'display_name': 'Paneer',
                        'multiplier': 1.2
                    },
                    {
                        'value': 'Veggie',
                        'display_name': 'Veggie',
                        'multiplier': 1.1
                    },
                    {
                        'value': 'Chicken',
                        'display_name': 'Chicken',
                        'multiplier': 1.3
                    }
                ]
            },
            'Toppings': {
                'description': 'Additional pizza toppings',
                'options': [
                    {
                        'value': 'Onion',
                        'display_name': 'Onion',
                        'multiplier': 1.02
                    },
                    {
                        'value': 'Capsicum',
                        'display_name': 'Capsicum',
                        'multiplier': 1.02
                    },
                    {
                        'value': 'Corn',
                        'display_name': 'Corn',
                        'multiplier': 1.05
                    },
                    {
                        'value': 'Mushroom',
                        'display_name': 'Mushroom',
                        'multiplier': 1.04
                    },
                    {
                        'value': 'Paneer',
                        'display_name': 'Paneer',
                        'multiplier': 1.10
                    },
                    {
                        'value': 'Olives',
                        'display_name': 'Olives',
                        'multiplier': 1.03
                    }
                ]
            },
            'Burger Type': {
                'description': 'Type of burger',
                'options': [
                    {'value': 'Veg', 'display_name': 'Veg Burger', 'multiplier': 1.0},
                    {'value': 'Aloo Tikki',
                        'display_name': 'Aloo Tikki Burger', 'multiplier': 1.05},
                    {'value': 'Paneer', 'display_name': 'Paneer Burger',
                        'multiplier': 1.2},
                    {'value': 'Chicken', 'display_name': 'Chicken Burger',
                        'multiplier': 1.3},
                    {'value': 'Fish', 'display_name': 'Fish Burger', 'multiplier': 1.25},
                ]
            },
            'Burger Size': {
                'description': 'Size of burger',
                'options': [
                    {'value': 'Regular', 'display_name': 'Regular', 'multiplier': 1.0},
                    {'value': 'Large', 'display_name': 'Large', 'multiplier': 1.5},
                ]
            },

            'Burger Add-ons': {
                'description': 'Additional burger add-ons',
                'options': [
                    {'value': 'None', 'display_name': 'None', 'multiplier': 1.0},
                    {'value': 'Mayo', 'display_name': 'Extra Mayo', 'multiplier': 1.05},
                    {'value': 'Extra Sauce',
                        'display_name': 'Extra Sauce', 'multiplier': 1.05},
                    {'value': 'Extra Patty',
                        'display_name': 'Extra Patty', 'multiplier': 1.5},
                ]
            },
            'Patty Count': {
                'description': 'Number of patties',
                'options': [
                    {'value': 'Single', 'display_name': 'Single Patty',
                        'multiplier': 1.0},
                    {'value': 'Double', 'display_name': 'Double Patty',
                        'multiplier': 1.8},
                ]
            },
            'Cooking Style': {
                'description': 'How the rice is cooked',
                'options': [
                    {'value': 'White Rice',
                        'display_name': 'White Rice', 'multiplier': 1.0},
                    {'value': 'Brown Rice', 'display_name': 'Brown Rice',
                        'multiplier': 1.05},
                    {'value': 'Basmati', 'display_name': 'Basmati Rice',
                        'multiplier': 0.98},
                    {'value': 'Parboiled', 'display_name': 'Parboiled Rice',
                        'multiplier': 1.02},
                ]
            },
            'Rice Type': {
                'description': 'Type of rice preparation',
                'options': [
                    {'value': 'Plain Rice',
                        'display_name': 'Plain Rice', 'multiplier': 1.0},
                    {'value': 'Jeera Rice',
                        'display_name': 'Jeera Rice', 'multiplier': 1.1},
                    {'value': 'Veg Pulao', 'display_name': 'Veg Pulao',
                        'multiplier': 1.25},
                    {'value': 'Chicken Biryani',
                     'display_name': 'Chicken Biryani', 'multiplier': 1.6},
                    {'value': 'Veg Biryani',
                        'display_name': 'Veg Biryani', 'multiplier': 1.4},
                ]
            },
            'Portion Size': {
                'description': 'Serving size',
                'options': [
                    {'value': 'Small', 'display_name': 'Small', 'multiplier': 0.75},
                    {'value': 'Medium', 'display_name': 'Medium', 'multiplier': 1.0},
                    {'value': 'Large', 'display_name': 'Large', 'multiplier': 1.5},
                ]
            },
            'Biryani Type': {
                'description': 'Type of biryani',
                'options': [
                    {'value': 'Veg', 'display_name': 'Veg Biryani', 'multiplier': 1.0},
                    {'value': 'Paneer', 'display_name': 'Paneer Biryani',
                        'multiplier': 1.1},
                    {'value': 'Egg', 'display_name': 'Egg Biryani', 'multiplier': 1.15},
                    {'value': 'Chicken', 'display_name': 'Chicken Biryani',
                        'multiplier': 1.25},
                    {'value': 'Mutton', 'display_name': 'Mutton Biryani',
                        'multiplier': 1.4},
                ]
            },
            'Spice Level': {
                'description': 'Spice level of biryani',
                'options': [
                    {'value': 'Mild', 'display_name': 'Mild', 'multiplier': 1.0},
                    {'value': 'Medium', 'display_name': 'Medium', 'multiplier': 1.02},
                    {'value': 'Spicy', 'display_name': 'Spicy', 'multiplier': 1.05},
                ]
            },
            'Paratha Type': {
                'description': 'Type of paratha',
                'options': [
                    {'value': 'Plain', 'display_name': 'Plain Paratha',
                        'multiplier': 1.0},
                    {'value': 'Aloo', 'display_name': 'Aloo Paratha', 'multiplier': 1.2},
                    {'value': 'Gobhi', 'display_name': 'Gobhi Paratha',
                        'multiplier': 1.15},
                    {'value': 'Paneer', 'display_name': 'Paneer Paratha',
                        'multiplier': 1.3},
                ]
            },
            'Ghee Level': {
                'description': 'Amount of ghee/butter',
                'options': [
                    {'value': 'None', 'display_name': 'No Ghee', 'multiplier': 0.9},
                    {'value': 'Regular', 'display_name': 'Regular Ghee',
                        'multiplier': 1.0},
                    {'value': 'Extra', 'display_name': 'Extra Ghee', 'multiplier': 1.2},
                ]
            },
            'Dosa Type': {
                'description': 'Type of dosa',
                'options': [
                    {'value': 'Plain', 'display_name': 'Plain Dosa', 'multiplier': 1.0},
                    {'value': 'Masala', 'display_name': 'Masala Dosa',
                        'multiplier': 1.4},
                    {'value': 'Rava', 'display_name': 'Rava Dosa', 'multiplier': 1.15},
                    {'value': 'Mysore', 'display_name': 'Mysore Dosa',
                        'multiplier': 1.5},
                ]
            },
            'Idli Type': {
                'description': 'Type of idli',
                'options': [
                    {'value': 'Plain', 'display_name': 'Plain Idli', 'multiplier': 1.0},
                    {'value': 'Rava', 'display_name': 'Rava Idli', 'multiplier': 1.15},
                ]
            },
            'Momos Type': {
                'description': 'Type of momos',
                'options': [
                    {'value': 'Veg', 'display_name': 'Veg Momos', 'multiplier': 1.0},
                    {'value': 'Paneer', 'display_name': 'Paneer Momos',
                        'multiplier': 1.15},
                    {'value': 'Chicken', 'display_name': 'Chicken Momos',
                        'multiplier': 1.25},
                ]
            },
            'Preparation Type': {
                'description': 'Cooking style',
                'options': [
                    {'value': 'Steamed', 'display_name': 'Steamed', 'multiplier': 1.0},
                    {'value': 'Fried', 'display_name': 'Fried', 'multiplier': 1.4},
                ]
            },
            'Tea Type': {
                'description': 'Type of tea',
                'options': [
                    {'value': 'Milk Tea', 'display_name': 'Milk Tea', 'multiplier': 1.0},
                    {'value': 'Black Tea', 'display_name': 'Black Tea',
                        'multiplier': 0.3},
                    {'value': 'Green Tea', 'display_name': 'Green Tea',
                        'multiplier': 0.1},
                ]
            },
            'Sugar Level': {
                'description': 'Sugar added',
                'options': [
                    {'value': 'No Sugar', 'display_name': 'No Sugar', 'multiplier': 0.8},
                    {'value': '1 Tsp', 'display_name': '1 Tsp Sugar', 'multiplier': 1.0},
                    {'value': '2 Tsp', 'display_name': '2 Tsp Sugar',
                        'multiplier': 1.25},
                ]
            },
            'Coffee Type': {
                'description': 'Type of coffee',
                'options': [
                    {'value': 'Black', 'display_name': 'Black Coffee',
                        'multiplier': 0.2},
                    {'value': 'Milk', 'display_name': 'Milk Coffee', 'multiplier': 1.0},
                    {'value': 'Cold', 'display_name': 'Cold Coffee', 'multiplier': 1.6},
                ]
            },
            'Juice Type': {
                'description': 'Type of juice',
                'options': [
                    {'value': 'Orange', 'display_name': 'Orange Juice',
                        'multiplier': 1.0},
                    {'value': 'Apple', 'display_name': 'Apple Juice',
                        'multiplier': 1.05},
                    {'value': 'Mango', 'display_name': 'Mango Juice', 'multiplier': 1.3},
                    {'value': 'Mixed Fruit',
                        'display_name': 'Mixed Fruit Juice', 'multiplier': 1.15},
                ]
            },
            'Sugar Added': {
                'description': 'Added sugar',
                'options': [
                    {'value': 'No', 'display_name': 'No Added Sugar', 'multiplier': 1.0},
                    {'value': 'Yes', 'display_name': 'Added Sugar', 'multiplier': 1.25},
                ]
            },
            'Ice Cream Type': {
                'description': 'Flavor',
                'options': [
                    {'value': 'Vanilla', 'display_name': 'Vanilla', 'multiplier': 1.0},
                    {'value': 'Chocolate', 'display_name': 'Chocolate',
                        'multiplier': 1.1},
                    {'value': 'Butterscotch',
                        'display_name': 'Butterscotch', 'multiplier': 1.15},
                    {'value': 'Kulfi', 'display_name': 'Kulfi', 'multiplier': 1.2},
                ]
            },
        }

        # Create attributes and options
        created_attrs = {}
        for attr_name, attr_data in attributes.items():
            if not force and FoodAttribute.objects.filter(name=attr_name).exists():
                attr = FoodAttribute.objects.get(name=attr_name)
                self.stdout.write(f'✓ Attribute "{attr_name}" already exists')
            else:
                attr, created = FoodAttribute.objects.get_or_create(
                    name=attr_name,
                    defaults={'description': attr_data['description']}
                )
                action = 'Created' if created else 'Updated'
                self.stdout.write(self.style.SUCCESS(
                    f'  ✓ {action} attribute: {attr_name}'))

            # Create options
            for option_data in attr_data['options']:
                opt, created = FoodAttributeOption.objects.get_or_create(
                    attribute=attr,
                    value=option_data['value'],
                    defaults={
                        'display_name': option_data['display_name'],
                        'nutrition_multiplier': option_data['multiplier'],
                    }
                )
                if created:
                    self.stdout.write(
                        f'    → {option_data["display_name"]} ({option_data["multiplier"]}x)')

            created_attrs[attr_name] = attr

        # ========== LINK ATTRIBUTES TO FOODS ==========
        food_links = food_links = FOOD_LINKS

        self.stdout.write('\n📦 Linking attributes to foods...')

        for food_name, attrs in food_links.items():
            # Try to find the food
            food = FoodItem.objects.filter(name__iexact=food_name).first()
            if not food:
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠️  Food "{food_name}" not found in database. Skipping...')
                )
                continue

            for attr_name, order, is_required in attrs:
                if attr_name not in created_attrs:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ⚠️  Attribute "{attr_name}" not found. Skipping...')
                    )
                    continue

                attr = created_attrs[attr_name]
                fattr, created = FoodItemAttribute.objects.get_or_create(
                    food_item=food,
                    attribute=attr,
                    defaults={'order': order, 'is_required': is_required}
                )
                action = '✓ Linked' if created else '✓ Already linked'
                req_str = '(required)' if is_required else '(optional)'
                self.stdout.write(
                    f'  {action}: {food_name} → {attr_name} {req_str}')

        self.stdout.write(self.style.SUCCESS(
            '\n✅ Food attributes setup complete!'))
        self.stdout.write('\n📚 Next steps:')
        self.stdout.write('  1. Test the APIs:')
        self.stdout.write('     GET /userFood/foods/1/attributes/')
        self.stdout.write('     GET /userFood/attributes/1/options/')
        self.stdout.write('  2. Log a meal with attributes:')
        self.stdout.write('     POST /userFood/logmeals_with_attributes/')
        self.stdout.write('  3. Check the database:')
        self.stdout.write('     python manage.py dbshell')
        self.stdout.write('     SELECT * FROM userFood_foodattribute;')
        self.stdout.write('     SELECT * FROM userFood_foodattributeoption;')
        self.stdout.write('     SELECT * FROM userFood_fooditemattribute;')
