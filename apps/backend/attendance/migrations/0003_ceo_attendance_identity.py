from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [("attendance", "0002_alter_attendancepolicy_workday_end_and_more")]

    operations = [
        migrations.AlterField(model_name="attendancerecord", name="employee", field=models.ForeignKey(blank=True, null=True, on_delete=models.PROTECT, related_name="attendance_records", to="organizations.employeeprofile")),
        migrations.AlterField(model_name="attendancerecord", name="branch", field=models.ForeignKey(blank=True, null=True, on_delete=models.PROTECT, related_name="attendance_records", to="organizations.branch")),
        migrations.AddField(model_name="attendancerecord", name="attendance_user", field=models.ForeignKey(blank=True, null=True, on_delete=models.PROTECT, related_name="personal_attendance_records", to=settings.AUTH_USER_MODEL)),
        migrations.AddConstraint(model_name="attendancerecord", constraint=models.UniqueConstraint(condition=Q(attendance_user__isnull=False), fields=("attendance_user", "attendance_date"), name="unique_user_attendance_date")),
    ]
