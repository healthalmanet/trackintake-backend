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
        food_links = {
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
                ('Sugar Level', 1, False),
            ],
            'Pizza': [
                ('Size', 1, True),
                ('Crust Type', 2, True),
            ],
        }

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
