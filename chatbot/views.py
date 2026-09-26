# chatbot/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.parsers import JSONParser
import re
from rest_framework.permissions import AllowAny


    
# MENU DATA
# ---------------------------
MENU_DATA = {
    "About TrackIntake": "TrackIntake is an AI-powered nutrition and health tracking platform that helps you log your daily meals, monitor your nutrition, and receive personalized diet recommendations.",
    "Data & Security": "Your data is safe, secure, and never shared without your permission.",
    "Contact Us": "📞 7898622813"
}

# ---------------------------
# USER FAQ
# ---------------------------
USERSECTIONS = {

  "How to Use": [
    { "q": "How do I start using TrackIntake?", "a": "Create an account, complete your profile, and start logging your meals." },
    { "q": "What details are required first?", "a": "You need to enter basic details like age, weight, height, and your health goals." },
    { "q": "Is it easy for beginners?", "a": "Yes, the platform is simple and designed for all users." },
    { "q": "Do I need to use it daily?", "a": "Daily usage helps in better tracking and accurate results." },
    { "q": "Can I skip profile setup?", "a": "Yes, but completing your profile gives better recommendations." }
  ],

  "Track Meals": [
    { "q": "How do I log my meals?", "a": "You can type your food items and the system will calculate calories automatically." },
    { "q": "Can I edit my meals later?", "a": "Yes, you can edit or delete your meal entries anytime." },
    { "q": "How are meals organized?", "a": "Meals are divided into breakfast, lunch, dinner, and snacks." },
    { "q": "Does it support Indian food?", "a": "Yes, it includes a variety of Indian food items." },
    { "q": "Is there a food search option?", "a": "Search options may be limited but can be improved in future updates." }
  ],

  "Diet Plans": [
    { "q": "How do I get diet plans?", "a": "Diet plans are generated based on your profile and health goals." },
    { "q": "Are diet plans personalized?", "a": "Yes, plans are customized according to your data." },
    { "q": "Can I follow plans without a nutritionist?", "a": "Yes, but expert advice can improve results." },
    { "q": "Will veg preference be followed?", "a": "The system tries to follow your preference, but improvements may be needed." },
    { "q": "Are diet plans accurate?", "a": "They are based on standard nutrition data." }
  ],

  "Health Tracking": [
    { "q": "What health tools are available?", "a": "BMI calculator, water tracker, and weight tracker are available." },
    { "q": "Can I track my BMI?", "a": "Yes, you can calculate BMI by entering your height and weight." },
    { "q": "Is BMI feature free?", "a": "Basic BMI results are free, advanced insights may require premium." },
    { "q": "Can I track water intake?", "a": "Yes, you can monitor your daily water intake." },
    { "q": "Can I track my weight?", "a": "Yes, weight tracking helps you monitor progress over time." },
    { "q": "Is this platform suitable for diabetes or heart patients?", "a": "Yes, TrackIntake supports diabetes management, heart health, weight loss, and other lifestyle conditions." }
  ],

  "My Progress": [
    { "q": "Can I see my progress?", "a": "Yes, your progress is shown on the dashboard." },
    { "q": "What does the dashboard show?", "a": "It shows calories, water intake, and weight summary." },
    { "q": "Can I track long-term progress?", "a": "Yes, you can view trends over time." },
    { "q": "Does it help with motivation?", "a": "Yes, tracking progress helps you stay consistent." },
    { "q": "Is progress tracking automatic?", "a": "Yes, it updates based on your logged data." }
  ],

  
  "Help & Support": [
    { "q": "Can I contact support?", "a": "Yes, support is available for help." },
    { "q": "Can I consult a nutritionist?", "a": "Yes, you can connect with a nutritionist." },
    { "q": "What should I do if I face issues?", "a": "You can contact the support team." },
    { "q": "Is help available anytime?", "a": "Support availability may vary." },
    { "q": "Can I give feedback?", "a": "Yes, your feedback helps improve the platform." }
  ]
}

NUTRITIONSECTIONS = {

   "How to Use": [
    { "q": "How do I start using TrackIntake as a nutritionist?", "a": "Register on the platform, complete your professional profile, and start using the features." },
    { "q": "What details are required during setup?", "a": "You need to enter your professional details like experience, specialization, and profile information." },
    { "q": "Is the platform easy to use?", "a": "Yes, it is designed to be simple and user-friendly." },
    { "q": "Do I need training before using it?", "a": "Basic onboarding or demo support is available to help you understand the platform." },
    { "q": "Can I start working immediately?", "a": "Yes, once your profile is complete, you can start managing patients and creating diet plans." }
  ],

  "Patients": [
    { "q": "Can I manage multiple patients?", "a": "Yes, you can manage multiple patients from one dashboard depending on your plan." },
    { "q": "Can I monitor patients daily?", "a": "Yes, you can track daily meals, calorie intake, and health progress." },
    { "q": "Can I get new patients through the platform?", "a": "Yes, the platform helps you connect with new patients." },
    { "q": "How can I track patient progress?", "a": "You can view meal logs, reports, and progress data from your dashboard." },
    { "q": "Is patient data easy to access?", "a": "Yes, all patient information is organized and easy to access." }
  ],

  "Diet Plans": [
    { "q": "How do I create diet plans?", "a": "You can create plans using templates, food database, and AI suggestions." },
    { "q": "Can I customize diet plans?", "a": "Yes, diet plans can be fully customized based on patient needs." },
    { "q": "Does the system support Indian diets?", "a": "Yes, it includes a wide range of Indian food options." },
    { "q": "Can I reuse diet plans?", "a": "Yes, you can reuse and modify plans for different patients." },
    { "q": "Does AI help in diet planning?", "a": "Yes, AI provides suggestions to make planning faster and easier." }
  ],

  "Consultations": [
    { "q": "Can I conduct online consultations?", "a": "Yes, you can provide online consultations and follow-ups." },
    { "q": "Can I communicate with patients easily?", "a": "Yes, the platform allows easy communication with patients." },
    { "q": "Can I schedule consultations?", "a": "Yes, you can manage and schedule your sessions." },
    { "q": "Is follow-up support available?", "a": "Yes, you can provide continuous follow-up support." },
    { "q": "Is it convenient for both sides?", "a": "Yes, it is flexible and convenient for both nutritionists and patients." }
  ],

  "Earnings": [
    { "q": "How can I earn through TrackIntake?", "a": "You can earn through consultations, diet plans, and subscription services." },
    { "q": "Are there multiple earning options?", "a": "Yes, you can offer different services to generate income." },
    { "q": "Can I set my own pricing?", "a": "In most cases, you can customize pricing based on your services." },
    { "q": "Can this help grow my practice?", "a": "Yes, it helps you reach more clients and expand your work." },
    { "q": "Can I track my earnings?", "a": "Yes, you can monitor your income and transactions." }
  ],

  "Reports": [
    { "q": "Can I generate patient reports?", "a": "Yes, you can generate detailed reports for each patient." },
    { "q": "What insights are available?", "a": "You get insights on nutrition, calories, and health progress." },
    { "q": "Can I track long-term progress?", "a": "Yes, long-term tracking is available." },
    { "q": "Are reports easy to understand?", "a": "Yes, reports are simple and clear." },
    { "q": "Can I use data for research?", "a": "Yes, data can be useful for research and case studies." }
  ],

  "Help & Support": [
    { "q": "What should I do if I face issues?", "a": "You can contact the support team for help." },
    { "q": "Is technical support available?", "a": "Yes, support is available for technical issues." },
    { "q": "Can I request a demo?", "a": "Yes, demo sessions can help you understand features better." },
    { "q": "How can I contact support?", "a": "You can use email or contact options provided on the platform." },
    { "q": "Can I give feedback?", "a": "Yes, your feedback helps improve the platform." }
  ]
  
  }


# ---------------------------
# API VIEW
# ---------------------------
import os
import re
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny

try:
    from google import genai
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
except Exception:
    ai_client = None


@method_decorator(csrf_exempt, name='dispatch')
class ChatBotView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"message": "Use POST method with {'question': '...', 'role': 'user|nutritionist'}"})

    def post(self, request):
        try:
            raw_question = request.data.get("question", "").strip()
            role = request.data.get("role", "user").lower().strip()
            if not raw_question:
                return Response({"answer": "Please ask a question about your diet, meals, or TrackIntake features."})

            cleaned_q = re.sub(r'[^\w\s]', '', raw_question.lower())
            question_words = set(cleaned_q.split())

            # 🔹 Role-specific FAQs first
            active_sections = NUTRITIONSECTIONS if role == "nutritionist" else USERSECTIONS
            all_faqs = []
            for section in active_sections.values():
                all_faqs.extend(section)

            # 🔥 SMART MATCHING FOR HIGH-CONFIDENCE FAQ MATCHES
            best_match = None
            max_score = 0
            for item in all_faqs:
                q_clean = re.sub(r'[^\w\s]', '', item["q"].lower())
                q_words = set(q_clean.split())
                score = len(question_words & q_words)
                if score > max_score:
                    max_score = score
                    best_match = item

            # If high-confidence match found (3+ overlapping keywords or exact match)
            if max_score >= 3 and best_match:
                return Response({
                    "answer": best_match["a"],
                    "source": "faq"
                })

            # 🔹 Dynamic AI Generation using Gemini
            if ai_client:
                role_context = "a registered clinical nutritionist / dietitian" if role == "nutritionist" else "a patient / health tracking user"
                system_prompt = f"""You are the official TrackIntake AI Health & Clinical Assistant.
TrackIntake is an advanced clinical dietary nutrition and health tracking platform.

Platform Core Capabilities:
1. Patient Assignment & Practitioner Practice:
   - Nutritionists can register/create new patients manually via 'Add Patient' (name, email, age, gender, dietary preferences, health goals), which automatically assigns the patient to their roster.
   - Nutritionists can bulk import multiple patients at once using our pre-filled Excel template (.xlsx) containing realistic sample records.
   - Nutritionists can assign existing platform users, view daily food logs & macro summaries, approve AI diet recommendations, manage patient lab reports, and switch patients inside Quick Tools.
   - Availability management: practitioners configure working days, slot durations (15/30/45/60 min), buffers, and 'Pay at Clinic' cash booking options.

2. Patient Health Tools & Tracking:
   - Meal Logging: Log Indian and international meals using household measures (Katoris, bowls, plates, rotis) or exact grams (g)/milliliters (ml) with live calorie, carb, protein, fat tracking, and food suggestions.
   - Diet Plans: Access personalized 3-day and 15-day clinical meal plans prescribed by nutritionist or generated by AI, with one-click 'Log this Diet Meal'.
   - Water Tracker: Track hydration with quick +250ml cup, +500ml bottle, +1L bottle increments, and view 7-day hydration streaks.
   - BMI Calculator: Calculate Body Mass Index and find clinical healthy weight target ranges.
   - Body Fat Calculator: Estimate body fat % and lean muscle mass using the US Navy circumference method (neck, waist, hip).
   - Weight Tracker: Log body weight history, visualize progress curves, and track pacing toward target weight goals.
   - Custom Reminders: Schedule personalized in-app notifications for meal times, water intake, vitamins/medications, and weigh-in days.
   - Health Dashboard & Diabetes Vitals: Log and monitor Fasting and Post-Prandial blood glucose, blood pressure, and heart rate.
   - Lab Reports: Upload medical test PDFs/images (CBC, Lipid, HbA1c, Thyroid) to share directly with assigned nutritionists.
   - Nutrition Search: Database of 2000+ Indian and global foods with Glycemic Index (GI), macros, and micronutrients.
   - Appointments: Book in-person clinic visits or online video consultations, with online payment via Razorpay or Pay at Clinic.
   - Direct Communication: Bidirectional chat between patients and certified dietitians with quick clinical response snippets.

The user interacting with you has the role: {role_context}.
User Question: "{raw_question}"

Instructions:
1. Provide practical, empathetic, and scientifically validated health and nutrition guidance.
2. Specialize in Indian dietary practices (dal, roti, paneer, khichdi, idli, rice, sabzi, curd, lassi, sprouts, etc.) with realistic portion guidance.
3. If they ask about TrackIntake features (how to add patients, bulk upload, log meals, track water, calculate BMI or body fat, upload lab reports), provide exact, actionable step-by-step instructions.
4. Format your answer with clean Markdown (bullet points, bold text). Keep responses concise, clear, and easy to read.
"""
                try:
                    ai_response = ai_client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=system_prompt
                    )
                    answer_text = (ai_response.text or "").strip()
                    if answer_text:
                        return Response({
                            "answer": answer_text,
                            "source": "gemini"
                        })
                except Exception as ai_err:
                    print(f"ChatBot Gemini error: {ai_err}")

            # Fallback to best FAQ match if score >= 2
            if max_score >= 2 and best_match:
                return Response({
                    "answer": best_match["a"],
                    "source": "faq_fallback"
                })

            # Default helpful clinical summary
            default_answer = (
                "### 💡 TrackIntake Assistant\n\n"
                "• **Meal Logging**: Head to Meal Logger or your Dashboard to log meals using standard units like Bowls, Plates, or exact grams.\n"
                "• **Water Tracking**: Log your daily hydration in the Water Tracker.\n"
                "• **Personalized Plans**: View your 3-day AI diet plan in the Diet section or connect with your nutritionist for tailored adjustments."
            )
            return Response({"answer": default_answer, "source": "default"})

        except Exception as e:
            return Response({
                "answer": "I am currently optimizing my response engine. Please ask your question again or check your meal logger.",
                "error": str(e)
            })