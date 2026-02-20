import os
import json
import google.generativeai as genai
from functools import wraps
from django.http import HttpResponseForbidden
from h11 import Response
from django.core.mail import send_mail
from twilio.rest import Client
from django.conf import settings
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
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

    email = EmailMultiAlternatives(subject, text_content, settings.EMAIL_HOST_USER, [to_email])
    email.attach_alternative(html_content, "text/html")
    try:
        email.send()
    except Exception as e:
        logger.warning(f"📭 Email failed but meal saved: {e}")





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

    email = EmailMultiAlternatives(subject, text_content, settings.EMAIL_HOST_USER, [to_email])
    email.attach_alternative(html_content, "text/html")
    try:
        email.send()
    except Exception as e:
        logger.warning(f"📭 Email failed but meal saved: {e}")




def send_sms_notification(to_number, message):
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    client.messages.create(
        body=message,
        from_=settings.TWILIO_PHONE_NUMBER,
        to=to_number
    )



def get_target_nutrients(user, current_date=None):
    from userProfile.models import UserProfile

    today = current_date or timezone.now().date()

    profile = UserProfile.objects.get(user=user)
    dob = profile.date_of_birth
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    weight, height = profile.weight_kg, profile.height_cm
    gender, activity_level, goal = profile.gender, profile.activity_level, profile.goal

    # BMR Calculation (Mifflin-St Jeor)
    bmr = 10 * weight + 6.25 * height - 5 * age + (5 if gender == "male" else -161)

    activity_multipliers = {
        "sedentary": 1.2,
        "light": 1.3,
        "lightly_active": 1.3,
        "moderate": 1.45,
        "active": 1.6,
        "very_active": 1.75
    }
    maintenance_calories = bmr * activity_multipliers.get(activity_level.lower(), 1.2)

    # Goal adjustment
    if goal.lower() == "gain weight":
        recommended_calories = maintenance_calories * 1.15
        target_weight = weight + 5
    elif goal.lower() == "lose weight":
        recommended_calories = maintenance_calories * 0.8
        target_weight = weight - 5
    else:
        recommended_calories = maintenance_calories
        target_weight = weight

    recommended_calories = round(recommended_calories)

    # Macronutrient targets
    protein_g = round(weight * 1.8)
    fats_g = round(weight * 0.8)
    protein_calories = protein_g * 4
    fats_calories = fats_g * 9
    carbs_calories = recommended_calories - (protein_calories + fats_calories)
    carbs_g = round(carbs_calories / 4) if carbs_calories > 0 else 0
    sugar_g = round((recommended_calories * 0.1) / 4)
    fiber_g = round((recommended_calories / 1000) * 14)

    # Water intake
    base_water_ml = weight * 35
    activity_water_bonus = {
        "sedentary": 0,
        "light": 250,
        "lightly_active": 250,
        "moderate": 500,
        "active": 750,
        "very_active": 1000
    }
    recommended_water_ml = base_water_ml + activity_water_bonus.get(activity_level.lower(), 0)

    return {
        "bmr": round(bmr),
        "maintenance_calories": round(maintenance_calories),
        "recommended_calories": recommended_calories,
        "macronutrients": {
            "protein_g": protein_g,
            "carbs_g": carbs_g,
            "fats_g": fats_g,
            "sugar_g": sugar_g,
            "fiber_g": fiber_g
        },
        "water": {"recommended_ml": round(recommended_water_ml)},
        "weight_target": {
            "current_weight_kg": round(weight, 1),
            "target_weight_kg": round(target_weight, 1),
            "goal": goal
        },
        "activity_level": activity_level
    }