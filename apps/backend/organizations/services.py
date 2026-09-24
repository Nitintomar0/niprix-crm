from rest_framework.exceptions import ValidationError


def validate_reporting_manager(profile, manager):
    if not manager:
        return
    if profile and manager.pk == profile.pk:
        raise ValidationError({"reporting_manager": "An employee cannot report to themselves."})
    if manager.branch.company_id != profile.branch.company_id:
        raise ValidationError({"reporting_manager": "Manager must belong to the same company."})
    cursor = manager
    seen = set()
    while cursor:
        if cursor.pk in seen or (profile and cursor.pk == profile.pk):
            raise ValidationError({"reporting_manager": "This assignment would create a reporting cycle."})
        seen.add(cursor.pk)
        cursor = cursor.reporting_manager
