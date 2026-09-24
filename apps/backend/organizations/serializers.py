from rest_framework import serializers

from .models import Branch, Company, Department, EmployeeProfile


class EmployeeProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)
    company = serializers.CharField(
        source="branch.company.name",
        read_only=True,
    )

    class Meta:
        model = EmployeeProfile
        fields = [
            "id",
            "user",
            "username",
            "email",
            "role",
            "company",
            "branch",
            "department",
            "employee_code",
            "phone",
            "joining_date",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "username",
            "email",
            "role",
            "company",
            "created_at",
            "updated_at",
        ]