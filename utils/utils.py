import os
import json
import google.generativeai as genai
from functools import wraps
from django.http import HttpResponseForbidden
from h11 import Response
from twilio.rest import Client
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


UNIT_TO_GRAMS = {
    "g": 1, "kg": 1000,
    "ml": 1, "l": 1000,
    "cup": 240, "bowl": 400,
    "piece": 100, "tbsp": 15,
    "tsp": 5, "slice": 30,
    "other": 100
}

def role_required(allowed_roles):
    def decorator(view_func):
        def _wrapped_view(self, *args, **kwargs):
            user = self.request.user
            if not user.is_authenticated:
                return Response({"detail": "Authentication required."}, status=401)
            if user.role not in allowed_roles:
                return Response({"detail": "Permission denied."}, status=403)
            return view_func(self, *args, **kwargs)
        return _wrapped_view
    return decorator


def send_email_notification_CALORIE(to_email, subject, message, calories, target_calories, date):
    subject = f"🎉 Daily Nutrition Summary – {date}"

    text_content = f"{subject}\n\n{message}\nCalories: {calories:.1f}/{target_calories:.1f}"

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: #ffffff; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); padding: 20px;">
            <h2 style="color: #4CAF50; text-align: center;">🥗 Daily Nutrition Summary</h2>
            <p style="text-align: center; color: #333; font-size: 16px;">For <b>{date}</b></p>
            
            <p style="color: #555;">{message}</p>
            
            <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                <tr style="background-color: #4CAF50; color: white;">
                    <th style="padding: 12px; border: 1px solid #ddd;">Metric</th>
                    <th style="padding: 12px; border: 1px solid #ddd;">Consumed</th>
                    <th style="padding: 12px; border: 1px solid #ddd;">Target</th>
                </tr>
                <tr>
                    <td style="padding: 12px; border: 1px solid #ddd;">Calories (kcal)</td>
                    <td style="padding: 12px; border: 1px solid #ddd; text-align: center;">{calories:.1f}</td>
                    <td style="padding: 12px; border: 1px solid #ddd; text-align: center;">{target_calories:.1f}</td>
                </tr>
            </table>

            <p style="margin-top: 25px; color: #444; font-size: 14px;">✅ Stay consistent with your meals and hit your goals!</p>
            
            <hr style="margin-top: 30px;">
            <p style="font-size: 12px; color: #888; text-align: center;">
                This is an automated message from <b>TrackEats</b>. You're receiving this because you logged your meals today.
            </p>
        </div>
    </body>
    </html>
    """

    from utils.resend_email import send_resend_email_async
    send_resend_email_async(
        to=to_email,
        subject=subject,
        html=html_content,
        text=text_content
    )


def send_email_notification_WATER(to_email, subject, message, consumed_ml, target_ml, date):
    subject = f"💧 Water Target Reached - {date}"

    text_content = f"{subject}\n\n{message}"

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2 style="color: #4CAF50;">💧 Water Target Completed - {date}</h2>
        <p>{message}</p>
        <table border="1" cellpadding="10" cellspacing="0" style="border-collapse: collapse;">
            <tr style="background-color: #f2f2f2;">
                <th>Metric</th><th>Consumed</th><th>Target</th>
            </tr>
            <tr>
                <td><b>Water (ml)</b></td><td>{consumed_ml:.1f}</td><td>{target_ml:.1f}</td>
            </tr>
        </table>
        <p style="margin-top:20px;">🚰 Keep drinking water regularly for better health.</p>
        <hr>
        <p style="font-size: 12px; color: #888;">This is an automated message from TrackEats.</p>
    </body>
    </html>
    """

    from utils.resend_email import send_resend_email_async
    send_resend_email_async(
        to=to_email,
        subject=subject,
        html=html_content,
        text=text_content
    )




def send_sms_notification(to_number, message):
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    client.messages.create(
        body=message,
        from_=settings.TWILIO_PHONE_NUMBER,
        to=to_number
    )



def calculate_target_nutrients(profile_or_user_or_dict, current_date=None) -> dict:
    """
    Canonical, unified calculation for BMR, maintenance calories, target calories,
    macronutrients, and hydration targets.
    Accepts:
      - dict (serialized profile data)
      - UserProfile model instance
      - User model instance
    """
    from datetime import date, datetime
    from userProfile.models import UserProfile

    today = current_date or timezone.now().date()
    if isinstance(today, datetime):
        today = today.date()

    # Normalize inputs to profile_dict
    profile_dict = {}
    if isinstance(profile_or_user_or_dict, dict):
        profile_dict = profile_or_user_or_dict
    elif hasattr(profile_or_user_or_dict, "userprofile"):
        p = profile_or_user_or_dict.userprofile
        profile_dict = {
            "date_of_birth": p.date_of_birth,
            "weight_kg": p.weight_kg,
            "height_cm": p.height_cm,
            "gender": p.gender,
            "activity_level": p.activity_level,
            "goal": p.goal,
            "is_pregnant": getattr(p, "is_pregnant", False),
            "is_breastfeeding": getattr(p, "is_breastfeeding", False),
            "current_trimester": getattr(p, "current_trimester", None),
        }
    elif isinstance(profile_or_user_or_dict, UserProfile):
        p = profile_or_user_or_dict
        profile_dict = {
            "date_of_birth": p.date_of_birth,
            "weight_kg": p.weight_kg,
            "height_cm": p.height_cm,
            "gender": p.gender,
            "activity_level": p.activity_level,
            "goal": p.goal,
            "is_pregnant": getattr(p, "is_pregnant", False),
            "is_breastfeeding": getattr(p, "is_breastfeeding", False),
            "current_trimester": getattr(p, "current_trimester", None),
        }
    else:
        try:
            p = UserProfile.objects.get(user=profile_or_user_or_dict)
            profile_dict = {
                "date_of_birth": p.date_of_birth,
                "weight_kg": p.weight_kg,
                "height_cm": p.height_cm,
                "gender": p.gender,
                "activity_level": p.activity_level,
                "goal": p.goal,
                "is_pregnant": getattr(p, "is_pregnant", False),
                "is_breastfeeding": getattr(p, "is_breastfeeding", False),
                "current_trimester": getattr(p, "current_trimester", None),
            }
        except Exception:
            profile_dict = {}

    # Calculate age safely
    dob_raw = profile_dict.get("date_of_birth")
    age = 30
    if dob_raw:
        if isinstance(dob_raw, (date, datetime)):
            dob = dob_raw if isinstance(dob_raw, date) else dob_raw.date()
            try:
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            except Exception:
                age = 30
        elif isinstance(dob_raw, str) and dob_raw.strip():
            try:
                dob = datetime.strptime(dob_raw.strip(), '%Y-%m-%d').date()
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            except Exception:
                age = 30

    try:
        weight = float(profile_dict.get("weight_kg") or 65.0)
    except (ValueError, TypeError):
        weight = 65.0

    try:
        height = float(profile_dict.get("height_cm") or 170.0)
    except (ValueError, TypeError):
        height = 170.0

    gender = str(profile_dict.get("gender") or "male").lower().strip()
    activity_level = str(profile_dict.get("activity_level") or "Sedentary")
    goal = str(profile_dict.get("goal") or "Maintain Weight")

    is_pregnant = bool(profile_dict.get("is_pregnant", False))
    is_breastfeeding = bool(profile_dict.get("is_breastfeeding", False))
    current_trimester = profile_dict.get("current_trimester")

    # 1. BMR Calculation (Mifflin-St Jeor formula)
    bmr = 10 * weight + 6.25 * height - 5 * age + (5 if gender == "male" else -161)

    # 2. Activity Multipliers (Standard Mifflin-St Jeor / Harris-Benedict)
    # Handles "Moderately Active", "moderately_active", "moderate", etc.
    act_clean = activity_level.lower().replace("_", " ").strip()
    if "extra" in act_clean:
        mult = 1.9
        water_bonus = 1200
    elif "very" in act_clean:
        mult = 1.725
        water_bonus = 1000
    elif "mod" in act_clean:
        mult = 1.55
        water_bonus = 500
    elif "light" in act_clean:
        mult = 1.375
        water_bonus = 250
    else:  # Sedentary or default
        mult = 1.2
        water_bonus = 0

    maintenance_calories = bmr * mult

    # 3. Goal Adjustment
    goal_clean = goal.lower()
    if "gain" in goal_clean:
        # Standard +15% calorie surplus for lean gain
        recommended_calories = maintenance_calories * 1.15
        target_weight = weight + 5.0
    elif "lose" in goal_clean:
        # Standard -20% calorie deficit for healthy fat loss
        recommended_calories = maintenance_calories * 0.80
        target_weight = weight - 5.0
    else:
        recommended_calories = maintenance_calories
        target_weight = weight

    # 4. Pregnancy & Lactation Adjustments (ACOG / Clinical Standards)
    is_female = gender != "male"
    if is_female:
        if is_pregnant:
            if current_trimester == 2:
                recommended_calories += 340
            elif current_trimester == 3:
                recommended_calories += 450
        elif is_breastfeeding:
            recommended_calories += 500

    recommended_calories = round(recommended_calories)

    # 5. Macronutrients Breakdown
    protein_g = round(weight * 1.8)
    if is_female and (is_pregnant or is_breastfeeding):
        protein_g = max(protein_g, round(weight * 1.1) + 25)

    fats_g = round(weight * 0.8)
    protein_calories = protein_g * 4
    fats_calories = fats_g * 9
    carbs_calories = recommended_calories - (protein_calories + fats_calories)
    carbs_g = round(carbs_calories / 4) if carbs_calories > 0 else 0
    sugar_g = round((recommended_calories * 0.1) / 4)
    fiber_g = round((recommended_calories / 1000) * 14)

    # 6. Hydration Target
    base_water_ml = weight * 35
    recommended_water_ml = round(base_water_ml + water_bonus)

    macronutrients = {
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fats_g": fats_g,
        "sugar_g": sugar_g,
        "fiber_g": fiber_g,
    }

    return {
        "bmr": round(bmr),
        "maintenance_calories": round(maintenance_calories),
        "recommended_calories": recommended_calories,
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fats_g": fats_g,
        "sugar_g": sugar_g,
        "fiber_g": fiber_g,
        "macronutrients": macronutrients,
        "water": {"recommended_ml": recommended_water_ml},
        "weight_target": {
            "current_weight_kg": round(weight, 1),
            "target_weight_kg": round(target_weight, 1),
            "goal": goal,
        },
        "activity_level": activity_level,
    }


def get_target_nutrients(user, current_date=None):
    """
    Public convenience accessor for user target nutrients, maintaining backward compatibility.
    """
    return calculate_target_nutrients(user, current_date=current_date)