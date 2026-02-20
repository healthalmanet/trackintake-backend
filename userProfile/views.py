from rest_framework import status, permissions, viewsets, filters
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework.views import APIView
from .models import UserProfile, LabReport
from .serializers import UserProfileSerializer, LabReportSerializer
from rest_framework.permissions import IsAuthenticated



class UserProfileView(APIView):
    """
    A single endpoint to handle the user's profile.
    - GET: Retrieves the current user's profile.
    - POST: Creates a profile for the user if it doesn't exist.
    - PUT/PATCH: Updates the existing profile.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get(self, request, *args, **kwargs):
        """Handles GET requests to fetch the profile."""
        try:
            profile = UserProfile.objects.get(user=request.user)
            serializer = self.serializer_class(profile)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except UserProfile.DoesNotExist:
            return Response({"error": "Profile not found. Please create one by sending a POST request to this endpoint."}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, *args, **kwargs):
        """Handles POST requests to create a new profile."""
        if UserProfile.objects.filter(user=request.user).exists():
            return Response({"error": "Profile already exists. To update, please use PUT or PATCH."}, status=status.HTTP_409_CONFLICT)
        
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, *args, **kwargs):
        """Handles PUT requests to update an existing profile completely."""
        try:
            profile = UserProfile.objects.get(user=request.user)
            serializer = self.serializer_class(profile, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except UserProfile.DoesNotExist:
            return Response({"error": "Profile not found. Please create one first using POST."}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, *args, **kwargs):
        """Handles PATCH requests for partial updates."""
        try:
            profile = UserProfile.objects.get(user=request.user)
            serializer = self.serializer_class(profile, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except UserProfile.DoesNotExist:
            return Response({"error": "Profile not found. Please create one first using POST."}, status=status.HTTP_404_NOT_FOUND)

class LabReportViewSet(viewsets.ModelViewSet):
    """
    A ViewSet for viewing and editing lab reports.
    Provides `list`, `create`, `retrieve`, `update`, `partial_update`, and `destroy` actions.
    """
    serializer_class = LabReportSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['report_date']
    search_fields = ['report_date']
    ordering_fields = ['report_date']

    def get_queryset(self):
        return LabReport.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)