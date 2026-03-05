# from celery import shared_task
# import traceback
# from .models import DietRecommendation
# from user.models import User

# # You'll likely need your AI service function
# from ml_model.src.generator import generate_diet_plan # IMPORTANT: Your AI logic should be in a function


# @shared_task
# def create_diet_plan_for_user(user_id, placeholder_plan_id):
#     """
#     This is the background task that runs on the Celery worker.
#     It can take as long as it needs without timing out.
#     """
#     print(f"CELERY TASK: Starting work for user_id={user_id}, plan_id={placeholder_plan_id}")

#     try:
#         # Find the placeholder record the view created
#         plan = DietRecommendation.objects.get(id=placeholder_plan_id, user_id=user_id)
#         user = plan.user

#         # 1. Run your slow AI generation function
#         ai_result_json = generate_diet_plan(user) # Pass the user or ID as needed

#         # 2. Update the plan record with the results
#         plan.meals = ai_result_json
#         plan.status = 'completed' # Or 'pending_review'
#         plan.notes = 'Plan generated successfully.'
#         plan.save()

#         print(f"CELERY TASK: Successfully finished plan_id={placeholder_plan_id}")
#         return f"Success for plan {placeholder_plan_id}"

#     except Exception as e:
#         print(f"CELERY TASK FAILED for plan_id={placeholder_plan_id}. Error: {e}")
#         traceback.print_exc()

#         # IMPORTANT: Mark the plan as failed in the database so the user knows
#         try:
#             plan = DietRecommendation.objects.get(id=placeholder_plan_id)
#             plan.status = 'failed'
#             plan.notes = f"An internal error occurred during generation: {str(e)}"
#             plan.save()
#         except DietRecommendation.DoesNotExist:
#             # Cannot even find the plan to mark it as failed.
#             pass

#         # Re-raise the exception so Celery's monitoring knows the task failed
#         raise
from celery import shared_task
from django.db import transaction, close_old_connections
from diet.models import DietRecommendation
from utils.generative import generate_ai_plan_for_patient
import traceback


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def generate_ai_diet_task(self, recommendation_id):

    plan = None

    try:
        # 🔴 Always clean stale DB connections
        close_old_connections()

        plan = DietRecommendation.objects.get(id=recommendation_id)

        if plan.status != "generating":
            return

        patient_id = plan.user.id
        nutritionist_id = plan.reviewed_by.id if plan.reviewed_by else None

        # 🔴 Close DB connection BEFORE long AI work
        close_old_connections()

        ai_plan_json, error = generate_ai_plan_for_patient(
            patient_id=patient_id,
            nutritionist_id=nutritionist_id
        )

        # 🔴 Close again before writing
        close_old_connections()

        # SHORT atomic write
        with transaction.atomic():
            plan = DietRecommendation.objects.select_for_update().get(id=recommendation_id)

            if plan.status != "generating":
                return

            if error:
                plan.status = "failed"
                plan.save(update_fields=["status"])
                return

            plan.meals = ai_plan_json
            plan.original_ai_plan = ai_plan_json
            plan.status = "pending"

            plan.save(update_fields=["meals", "original_ai_plan", "status"])

    except Exception:
        traceback.print_exc()

        try:
            close_old_connections()
            plan = DietRecommendation.objects.get(id=recommendation_id)
            plan.status = "failed"
            plan.save(update_fields=["status"])
        except Exception:
            pass
