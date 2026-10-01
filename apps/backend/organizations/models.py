from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=255, unique=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Branch(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="branches",
    )
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"],
                name="unique_branch_per_company",
            )
        ]

    def __str__(self):
        return f"{self.name} - {self.company.name}"


class Department(models.Model):
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="departments",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "name"],
                name="unique_department_per_branch",
            )
        ]

    def __str__(self):
        return f"{self.name} - {self.branch.name}"
    
    
from django.conf import settings


class EmployeeProfile(models.Model):
    class EmploymentStatus(models.TextChoices):
        ONBOARDING = "ONBOARDING", "Onboarding"
        ACTIVE = "ACTIVE", "Active"
        NOTICE_PERIOD = "NOTICE_PERIOD", "Notice period"
        INACTIVE = "INACTIVE", "Inactive"
        OFFBOARDED = "OFFBOARDED", "Offboarded"
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="employees",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="employees",
    )
    employee_code = models.CharField(
        max_length=50,
        unique=True,
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
    )
    profile_photo = models.FileField(upload_to="employee-profile-photos/%Y/%m/", blank=True)
    designation = models.CharField(max_length=120, blank=True)
    team = models.CharField(max_length=120, blank=True)
    personal_address = models.TextField(blank=True)
    employment_status = models.CharField(max_length=20, choices=EmploymentStatus.choices, default=EmploymentStatus.ACTIVE)
    last_working_date = models.DateField(null=True, blank=True)
    offboarding_reason = models.TextField(blank=True)
    joining_date = models.DateField(
        null=True,
        blank=True,
    )
    reporting_manager = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="direct_reports",
    )
    is_active = models.BooleanField(default=True)
    # A history-safe deletion removes a person from operational People views
    # while retained CRM, attendance, and audit foreign keys stay valid.
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    can_receive_leads = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee_code} - {self.user.username}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.department_id and self.branch_id and self.department.branch_id != self.branch_id:
            raise ValidationError({"department": "Department must belong to the selected branch."})
        if self.reporting_manager_id:
            if self.reporting_manager_id == self.id:
                raise ValidationError({"reporting_manager": "An employee cannot report to themselves."})
            if self.branch_id and self.reporting_manager.branch.company_id != self.branch.company_id:
                raise ValidationError({"reporting_manager": "Manager must belong to the same company."})
        if self.employment_status == self.EmploymentStatus.OFFBOARDED and not self.last_working_date:
            raise ValidationError({"last_working_date": "An offboarded employee needs a last working date."})
