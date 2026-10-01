from django.contrib import admin

from .models import FollowUp, FollowUpActivity, ReminderEvent, ReminderPreference, Task


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "assigned_to", "scheduled_at", "status", "priority")
    list_filter = ("status", "priority", "follow_up_type")
    search_fields = ("title", "description", "assigned_to__employee_code")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "assigned_to", "due_date", "status", "priority")
    list_filter = ("status", "priority")
    search_fields = ("title", "description", "assigned_to__employee_code")


admin.site.register(FollowUpActivity)
admin.site.register(ReminderPreference)
admin.site.register(ReminderEvent)
