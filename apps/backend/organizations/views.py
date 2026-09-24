from django.shortcuts import render

# Create your views here.
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import EmployeeProfile
from .serializers import EmployeeProfileSerializer


class EmployeeListView(generics.ListAPIView):
    serializer_class = EmployeeProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.role == "CEO":
            return EmployeeProfile.objects.filter(
                branch__company=user.company,
                is_active=True,
            ).select_related("user", "branch", "department")

        if hasattr(user, "employee_profile"):
            return EmployeeProfile.objects.filter(
                branch=user.employee_profile.branch,
                is_active=True,
            ).select_related("user", "branch", "department")

        return EmployeeProfile.objects.none()