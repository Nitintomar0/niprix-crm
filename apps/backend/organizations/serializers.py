from rest_framework import serializers

from accounts.models import User
from .models import Branch, Company, Department, EmployeeProfile
from .services import validate_reporting_manager


class EmployeeProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)
    company = serializers.CharField(
        source="branch.company.name",
        read_only=True,
    )
    reporting_manager_name = serializers.CharField(source="reporting_manager.user.username", read_only=True)

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
            "reporting_manager",
            "reporting_manager_name",
            "is_active",
            "created_at",
            "updated_at",
        ]


class EmployeeWriteSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username")
    email = serializers.EmailField(source="user.email")
    first_name = serializers.CharField(source="user.first_name", required=False, allow_blank=True)
    last_name = serializers.CharField(source="user.last_name", required=False, allow_blank=True)
    role = serializers.ChoiceField(source="user.role", choices=User.Role.choices, required=False)
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = EmployeeProfile
        fields = ["id", "username", "email", "first_name", "last_name", "password", "role", "branch", "department", "employee_code", "phone", "joining_date", "reporting_manager", "is_active"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        branch = attrs.get("branch", getattr(self.instance, "branch", None))
        department = attrs.get("department", getattr(self.instance, "department", None))
        manager = attrs.get("reporting_manager", getattr(self.instance, "reporting_manager", None))
        actor = self.context["request"].user
        company = actor.company or (getattr(actor, "employee_profile", None) and actor.employee_profile.branch.company)
        if not company or not branch or branch.company_id != company.id:
            raise serializers.ValidationError({"branch": "Branch must belong to your company."})
        if not department or department.branch_id != branch.id:
            raise serializers.ValidationError({"department": "Department must belong to the selected branch."})
        if manager:
            if manager.branch.company_id != company.id:
                raise serializers.ValidationError({"reporting_manager": "Manager must belong to your company."})
            # Use a transient profile only for company/cycle validation on create.
            subject = self.instance or EmployeeProfile(branch=branch)
            validate_reporting_manager(subject, manager)
        return attrs

    def create(self, validated_data):
        user_data = validated_data.pop("user")
        password = validated_data.pop("password", None)
        request = self.context["request"]
        company = request.user.company
        user = User(**user_data, company=company)
        user.set_password(password or User.objects.make_random_password())
        user.save()
        profile = EmployeeProfile.objects.create(user=user, **validated_data)
        return profile

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        password = validated_data.pop("password", None)
        for attr, value in user_data.items():
            setattr(instance.user, attr, value)
        if password:
            instance.user.set_password(password)
        instance.user.save()
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.full_clean()
        instance.save()
        return instance


class SelfServiceProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", required=False)
    first_name = serializers.CharField(source="user.first_name", required=False, allow_blank=True)
    last_name = serializers.CharField(source="user.last_name", required=False, allow_blank=True)

    class Meta:
        model = EmployeeProfile
        fields = ["phone", "email", "first_name", "last_name"]

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        for attr, value in user_data.items():
            setattr(instance.user, attr, value)
        instance.user.save(update_fields=list(user_data) or None)
        return super().update(instance, validated_data)
        read_only_fields = [
            "id",
            "username",
            "email",
            "role",
            "company",
            "created_at",
            "updated_at",
        ]
