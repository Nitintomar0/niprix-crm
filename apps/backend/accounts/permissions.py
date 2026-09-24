from rest_framework.permissions import BasePermission


class IsCEO(BasePermission):
    message = "Only CEO users can access this resource."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "CEO"
        )