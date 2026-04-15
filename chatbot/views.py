# chatbot/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.parsers import JSONParser
import re


    
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
# chatbot/views.py



@method_decorator(csrf_exempt, name='dispatch')
class ChatBotView(APIView):

    def get(self, request):
        return Response({"message": "Use POST method"})

    def post(self, request):
        try:
            # 🔹 Clean user question
            question = request.data.get("question", "").lower().strip()
            question = re.sub(r'[^\w\s]', '', question)  # remove punctuation

            # 🔹 Combine all FAQs
            all_data = []

            for section in USERSECTIONS.values():
                all_data.extend(section)
                
            for section in NUTRITIONSECTIONS.values():
                all_data.extend(section)


            # 🔥 SMART MATCHING FUNCTION
            def find_best_answer(question, data):
                question_words = set(question.split())

                best_match = None
                max_score = 0

                for item in data:
                    q = item["q"].lower().strip()
                    q = re.sub(r'[^\w\s]', '', q)

                    q_words = set(q.split())

                    # count matching words
                    score = len(question_words & q_words)

                    if score > max_score:
                        max_score = score
                        best_match = item

                # 🔹 threshold (important)
                if max_score >= 2:
                    return best_match["a"]

                return "Answer not found"

            # 🔹 Get answer
            answer = find_best_answer(question, all_data)

            return Response({
                "answer": answer
            })

        except Exception as e:
            return Response({
                "answer": "Server error",
                "error": str(e)
            })