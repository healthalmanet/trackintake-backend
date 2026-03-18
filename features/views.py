from rest_framework import viewsets, permissions, status, generics, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
import os
from django.contrib.postgres.search import TrigramSimilarity # Required for the new fuzzy search
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .tasks import send_and_reschedule_reminders
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Case, When, IntegerField, Sum
from django.db.models.functions import Length
from rest_framework.generics import ListAPIView
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import SearchFilter
from rest_framework.permissions import BasePermission, IsAuthenticated
from django.db.models.functions import Lower, Replace
from django.db.models import Value
from django.utils.dateparse import parse_date


from userFood.views import targetNutrients
from utils.gemini import fetch_nutrition_from_gemini, food_search_gemini
from utils.utils import get_target_nutrients, send_email_notification_WATER
from .models import WeightLog, WaterIntakeLog, CustomReminder, Message, Blog
from .serializers import WeightLogSerializer, WaterIntakeLogSerializer, CustomReminderSerializer, MessageSerializer, FoodItemSerializer2, BlogSerializer
from django.conf import settings
from nutritionist.models import PatientAssignment
from userFood.models import FoodItem
from utils.pagination import BlogPagination, StandardResultsSetPagination
from .tasks import send_message_notification
from subscriptions.utils import require_plan_feature,get_active_subscription


class WeightLogViewSet(viewsets.ModelViewSet):
    serializer_class = WeightLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = WeightLog.objects.all()
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['date']
    ordering_fields = ['date', 'time_logged']
    ordering = ['-time_logged']

    def get_queryset(self):
        return WeightLog.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        # serializer.save(user=self.request.user) Subscription added
        require_plan_feature(self.request.user, "weight_tracker_allowed")

        serializer.save(user=self.request.user)



class WaterIntakeLogViewSet(viewsets.ModelViewSet):
    queryset = WaterIntakeLog.objects.all()
    serializer_class = WaterIntakeLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['date']
    ordering_fields = ['date']
    ordering = ['-date']

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        # ✅ Optional date handling
        require_plan_feature(request.user, "water_intake_allowed")
        date_str = request.data.get('date')
        today = parse_date(date_str) if date_str else timezone.now().date()

        amount_ml = request.data.get('amount_ml')
        if amount_ml is None:
            return Response({'error': 'amount_ml is required'}, status=400)
        
        amount_ml = float(amount_ml)

        obj, created = WaterIntakeLog.objects.get_or_create(
            user=request.user,
            date=today,
            defaults={'amount_ml': amount_ml}
        )

        if not created:
            obj.amount_ml += amount_ml
            obj.save()

        # ✅ Get nutrient targets for this date
        target_data = get_target_nutrients(request.user, current_date=today)
        recommended_water_ml = target_data.get('water', {}).get('recommended_ml', 0)

        # ✅ Notification logic
        notifications = []
        if obj.amount_ml >= recommended_water_ml:
            notifications.append(f"🎉 You reached your daily water target ({recommended_water_ml} ml)!")

            # ✅ Send email if available
            if request.user.email:
                subject = f"💧 Daily Water Goal Achieved - {today}"
                message = (
                    f"Great job! You've consumed {obj.amount_ml} ml of water today, "
                    f"meeting your goal of {recommended_water_ml} ml. Stay hydrated! 💙"
                )
                send_email_notification_WATER(
                    request.user.email, subject, message,
                    obj.amount_ml, recommended_water_ml, today
                )

        response_data = {
            "message": "Water logged successfully.",
            "notifications": notifications,
            "data": self.get_serializer(obj).data,
            "recommended_target": recommended_water_ml,
            "total_consumed": obj.amount_ml
        }

        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='total')
    def total_water_intake(self, request):
        date = request.query_params.get('date')
        if not date:
            return Response({"error": "date query param required"}, status=400)

        total = self.get_queryset().filter(date=date).aggregate(
            total_ml=Sum('amount_ml')
        )['total_ml'] or 0

        return Response({"date": date, "total_water_ml": total})




class CustomReminderViewSet(viewsets.ModelViewSet):
    queryset = CustomReminder.objects.all()
    serializer_class = CustomReminderSerializer
    permission_classes = [permissions.IsAuthenticated]

    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['frequency', 'is_active']
    ordering_fields = ['reminder_time', 'created_at']
    ordering = ['reminder_time']

    def get_queryset(self):
    # ✅ No gate here — always allow reading existing data
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        # ✅ Gate only on creating new reminders
        require_plan_feature(self.request.user, "custom_reminder_allowed")
        serializer.save(user=self.request.user)



class CanSendMessage(BasePermission):
    """
    Custom permission:
    - Nutritionists → can send to assigned patients
    - Patients → can send to their assigned nutritionist
    """

    def has_permission(self, request, view):
        receiver_id = request.data.get('receiver')
        if not receiver_id:
            return False

        user = request.user

        # If user is a nutritionist, can only message assigned patients
        if getattr(user, 'role', None) == 'nutritionist':
            return PatientAssignment.objects.filter(nutritionist=user, patient_id=receiver_id).exists()

        # If user is a patient, can only message their assigned nutritionist
        if getattr(user, 'role', None) == 'user':
            return PatientAssignment.objects.filter(patient=user, nutritionist_id=receiver_id).exists()

        # Other roles (e.g., operator) → Denied
        return False

class SendMessageView(generics.CreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated, CanSendMessage]

    def perform_create(self, serializer):
        require_plan_feature(
            self.request.user,
            "chat_allowed"
        )
        receiver_id = self.request.data.get("receiver")
        message = serializer.save(sender=self.request.user, receiver_id=receiver_id)
        send_message_notification(self.request.user, message.receiver, message.text)




class MessageListView(generics.ListAPIView):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Message.objects.filter(
            Q(sender=self.request.user) | Q(receiver=self.request.user)
        ).order_by('-timestamp')        


class MarkMessagesReadView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        Message.objects.filter(receiver=user, is_read=False).update(is_read=True)
        return Response({"status": "✅ Messages marked as read"}, status=status.HTTP_200_OK)




def _get_normalized_name_annotations():
    """
    Returns the queryset annotations needed for a normalized name search.
    Encapsulating this avoids repeating the logic.
    """
    return {
        'normalized_name': Replace(
            Replace(
                Replace(Lower('name'), Value(' '), Value('')),  # remove spaces
                Value('-'), Value('')                          # remove dashes
            ),
            Value(':'), Value('')                              # remove colons
        )
    }


FUZZY_MATCH_THRESHOLD = 0.9


class FoodItemListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    queryset = FoodItem.objects.all()
    serializer_class = FoodItemSerializer2
    # filter_backends and search_fields remain commented out as per your original code.

    # The _normalize_text helper is no longer needed with the new search logic,
    # as we now use standard iexact and TrigramSimilarity instead of custom normalization.
    # It has been removed to avoid confusion. The new logic is more robust.
    
    def list(self, request, *args, **kwargs):
        require_plan_feature(request.user, "ai_diet_allowed")


        search_term = request.query_params.get('search', None)

        # If no search term, return the full (paginated) list as normal.
        # THIS BLOCK IS UNCHANGED.
        if not search_term:
            return super().list(request, *args, **kwargs)

        clean_name = search_term.strip().lower()
        print(f"🔍 Searching for: '{clean_name}'")

        db_queryset = None

        # --- TIER 1: Exact Match ---
        # First, try to find an exact (case-insensitive) match. This is the fastest and most accurate.
        exact_match_queryset = FoodItem.objects.filter(name__iexact=clean_name)
        if exact_match_queryset.exists():
            print(f"✅ DB Match (Exact) Found for '{clean_name}'")
            db_queryset = exact_match_queryset

        # --- TIER 2: Conditional Fuzzy Match ---
        # If no exact match, and the search term is multi-word, try a fuzzy match.
        # This prevents "Dal" from incorrectly matching "Dal Bati".
        if not db_queryset and len(clean_name.split()) > 1:
            fuzzy_match_queryset = FoodItem.objects.annotate(
                similarity=TrigramSimilarity('name', clean_name)
            ).filter(similarity__gt=FUZZY_MATCH_THRESHOLD).order_by('-similarity')

            if fuzzy_match_queryset.exists():
                print(f"✅ DB Match (Fuzzy) Found for '{clean_name}'")
                db_queryset = fuzzy_match_queryset

        # If a DB match was found in Tier 1 or Tier 2, return it.
        if db_queryset is not None:
            # The standard DRF pagination and response flow from your original code is used here.
            page = self.paginate_queryset(db_queryset)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # --- TIER 3: Gemini External API Fallback ---
        # This block is functionally identical to your original "TIER 2", just re-labeled.
        # All variable names and logic are preserved.
        print(f"🔥 No DB match for '{search_term}'. Falling back to Gemini service.")
        try:
            # Delegate the entire process to the service function.
            food_item_instance = food_search_gemini(search_term)

            if food_item_instance:
                # Create a queryset containing only this single new item.
                new_item_queryset = FoodItem.objects.filter(pk=food_item_instance.pk)

                # Paginate and serialize this single-item queryset.
                page = self.paginate_queryset(new_item_queryset)
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            print("❌ Gemini service ran but returned no valid instance.")

        except ValueError as e: # Catch specific error from the service.
            print(f"❌ Gemini Service Error: {e}")
        except Exception as e:
            print(f"❌ An unexpected error occurred during Gemini fallback: {e}")

        # --- TIER 4: Return Empty ---
        # This is identical to your original "TIER 3".
        # If both DB search and Gemini service fail, return an empty list.
        print(f"❌ No match found anywhere for '{search_term}'")
        return self.get_paginated_response([]) # Return empty paginated response


class BlogListCreateView(generics.ListCreateAPIView):
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
    queryset = Blog.objects.all().order_by('-created_at')
    serializer_class = BlogSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = StandardResultsSetPagination



# ✅ List View with No Authentication
class BlogListView(generics.ListAPIView):
    queryset = Blog.objects.all()
    serializer_class = BlogSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = BlogPagination



class BlogDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Blog.objects.all()
    serializer_class = BlogSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_update(self, serializer):
        if self.request.user != self.get_object().author:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You can only edit your own blogs.")
        serializer.save()

    def perform_destroy(self, instance):
        if self.request.user != instance.author:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You can only delete your own blogs.")
        instance.delete()





# ✅ Fix — check auth FIRST
@api_view(['POST'])
@permission_classes([AllowAny])
def trigger_reminder_check_securely(request):
    auth_header = request.headers.get('Authorization')
    expected_secret = f"Bearer {os.environ.get('CRON_SECRET')}"

    if not auth_header or auth_header != expected_secret:
        return JsonResponse({"detail": "Unauthorized"}, status=401)

    try:
        send_and_reschedule_reminders()
        return Response({"message": "✅ Reminder check process initiated."})
    except Exception:
        return JsonResponse({"status": "error"}, status=500)