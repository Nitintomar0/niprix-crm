from django.contrib import admin

from .models import Branch, Company, Department, EmployeeProfile


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "is_active", "created_at")
    search_fields = ("name", "email")


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "city", "is_active", "created_at")
    list_filter = ("company", "city", "is_active")
    search_fields = ("name", "city")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "branch", "is_active", "created_at")
    list_filter = ("branch", "is_active")
    search_fields = ("name",)
    

@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = (
        "employee_code",
        "user",
        "branch",
        "department",
        "is_active",
        "joining_date",
    )
    list_filter = (
        "branch",
        "department",
        "is_active",
    )
    search_fields = (
        "employee_code",
        "user__username",
        "user__email",
    )