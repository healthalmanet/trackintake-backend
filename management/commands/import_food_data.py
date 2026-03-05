# File: app/management/commands/import_food_data.py

import os
import pandas as pd
from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from userFood.models import FoodItem

class Command(BaseCommand):
    help = 'Imports food items from the specified XLSX file, converting blank numeric fields to 0.'

    COLUMN_MAPPING = {
        'Food_Item': 'name', 'Default_Quantity': 'default_quantity', 'Default_Type': 'default_unit',
        'Gram_Equivalent': 'gram_equivalent', 'Calories': 'calories', 'Protein': 'protein',
        'Carbs': 'carbs', 'Fats': 'fats', 'Sugar': 'sugar', 'Fiber': 'fiber',
        'Saturated_Fat/g': 'saturated_fat_g', 'Trans_Fat/g': 'trans_fat_g', 'Estimated_GI': 'estimated_gi',
        'Glycemic_Load': 'glycemic_load', 'Sodium/mg': 'sodium_mg', 'Potassium/mg': 'potassium_mg',
        'Iron/mg': 'iron_mg', 'Calcium/mg': 'calcium_mg', 'Iodine/mcg': 'iodine_mcg',
        'Zinc/mg': 'zinc_mg', 'Magnesium/mg': 'magnesium_mg', 'Selenium/mcg': 'selenium_mcg',
        'Cholesterol/mg': 'cholesterol_mg', 'Omega_3/g': 'omega_3_g', 'Vitamin_D/mcg': 'vitamin_d_mcg',
        'Vitamin_B12/mcg': 'vitamin_b12_mcg', 'Vegetarian': 'food_type', 'Meal_Type': 'meal_type',
        'FODMAP_Level': 'fodmap_level', 'Spice_Level': 'spice_level', 'Purine_Level': 'purine_level',
        'Allergens': 'allergens',
    }

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='The path to the XLSX file to import.')

    def handle(self, *args, **options):
        file_path = options['file_path']
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"File not found: {file_path}"))
            return

        self.stdout.write(self.style.SUCCESS(f"Starting import from {file_path}..."))

        df = pd.read_excel(file_path, engine='openpyxl')
        df.rename(columns={k: v for k, v in self.COLUMN_MAPPING.items() if k in df.columns}, inplace=True)

        existing_names = set(FoodItem.objects.values_list('name', flat=True))
        items_to_create = []
        errors, skipped_duplicates = [], 0
        processors = self.get_processors()

        for index, row in df.iterrows():
            data = {}
            for field_name, processor in processors.items():
                if field_name in df.columns:
                    data[field_name] = processor(row.get(field_name))

            if not data.get('name'):
                errors.append(f"Row {index + 2}: Name is missing.")
                continue

            if data['name'] in existing_names:
                skipped_duplicates += 1
                continue
            
            item = FoodItem(**data)
            try:
                item.full_clean()
                items_to_create.append(item)
                existing_names.add(item.name)
            except ValidationError as e:
                msgs = ', '.join([f"'{f}': {', '.join(m)}" for f, m in e.message_dict.items()])
                errors.append(f"Row {index + 2} ('{data.get('name', 'N/A')}'): Validation failed - {msgs}")

        if items_to_create:
            FoodItem.objects.bulk_create(items_to_create, batch_size=500)
            self.stdout.write(self.style.SUCCESS(f"Successfully imported {len(items_to_create)} new food items."))

        if skipped_duplicates > 0:
            self.stdout.write(self.style.WARNING(f"Skipped {skipped_duplicates} items that already exist in the database."))

        if errors:
            self.stdout.write(self.style.ERROR(f"\nEncountered {len(errors)} errors:"))
            for error in errors[:20]: self.stdout.write(self.style.ERROR(f"- {error}"))
            if len(errors) > 20: self.stdout.write(self.style.ERROR(f"...and {len(errors) - 20} more errors."))

    def get_processors(self):
        processors = {field: self.process_text_field for field in self.COLUMN_MAPPING.values()}
        
        float_fields = [
            'default_quantity', 'gram_equivalent', 'calories', 'protein', 'carbs', 'fats', 'sugar', 'fiber',
            'saturated_fat_g', 'trans_fat_g', 'estimated_gi', 'glycemic_load', 'sodium_mg', 'potassium_mg',
            'iron_mg', 'calcium_mg', 'iodine_mcg', 'zinc_mg', 'magnesium_mg', 'selenium_mcg',
            'cholesterol_mg', 'omega_3_g', 'vitamin_d_mcg', 'vitamin_b12_mcg'
        ]
        for f in float_fields:
            processors[f] = self.process_float_field
        
        processors.update({
            'name': self.process_name, 'food_type': self.process_food_type,
            'meal_type': self.process_meal_type, 'fodmap_level': self.process_level_field,
            'spice_level': self.process_level_field, 'purine_level': self.process_level_field,
        })
        return processors

    def process_text_field(self, value):
        if pd.isna(value): return ""
        return str(value).strip()

    def process_name(self, value):
        if pd.isna(value) or not str(value).strip(): return None
        return str(value).strip()

    def process_float_field(self, value):
        # THIS IS THE CHANGED FUNCTION
        if pd.isna(value) or str(value).strip().lower() in ['', 'none']:
            return 0.0  # Return 0 for blank cells
        try:
            return float(str(value).replace(' ', ''))
        except (ValueError, TypeError):
            return 0.0 # Return 0 if conversion fails

    def process_food_type(self, value):
        v = str(value).strip().lower()
        if not v or v == 'none': return "other"
        if "non-veg" in v: return "non_vegetarian"
        if "egg" in v: return "eggetarian"
        if "vegan" in v: return "vegan"
        if "veg" in v: return "vegetarian"
        return "other"
        
    def process_meal_type(self, value):
        if pd.isna(value): return ['lunch']

        text_to_db_value = {
            'early-morning': 'early_morning', 'breakfast': 'breakfast',
            'mid-morning snack': 'morning_snack', 'lunch': 'lunch',
            'afternoon snack': 'afternoon_snack', 'dinner': 'dinner',
            'bedtime': 'bedtime', 'snack': 'morning_snack', 'dessert': 'dinner',
        }
        
        found_meals = set()
        parts = str(value).split('/')
        for part in parts:
            clean_part = part.strip().lower()
            db_value = text_to_db_value.get(clean_part)
            if db_value:
                found_meals.add(db_value)

        if not found_meals: return ['lunch']
        return list(found_meals)

    def process_level_field(self, value):
        v = str(value).strip().lower()
        if v == 'moderate': return 'medium'
        if v == 'mild': return 'low'
        return v if v in {"low", "medium", "high", "none"} else "low"