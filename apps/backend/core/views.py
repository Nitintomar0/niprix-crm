from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.views import OptionalPageNumberPagination

from .models import Notification
from .serializers import NotificationSerializer


def _prepare_requester_reminders(user):
    if not user.company_id:
        return
    # No scheduler is configured in this deployment. Preparing only this
    # user's events here is tenant-safe and preserves the same idempotency
    # guarantees a scheduled worker would use.
    from workspace.services import prepare_reminder_events
    prepare_reminder_events(user=user)


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = OptionalPageNumberPagination

    def get_queryset(self):
        _prepare_requester_reminders(self.request.user)
        if not self.request.user.company_id:
            return Notification.objects.none()
        queryset = Notification.objects.filter(
            company_id=self.request.user.company_id,
            recipient=self.request.user,
        )
        unread = self.request.query_params.get("unread")
        if unread is not None:
            if unread not in {"true", "false"}:
                raise ValidationError({"unread": "Use true or false."})
            queryset = queryset.filter(is_read=unread == "true")
        return queryset


class NotificationUnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _prepare_requester_reminders(request.user)
        count = Notification.objects.filter(
            company_id=request.user.company_id,
            recipient=request.user,
            is_read=False,
        ).count() if request.user.company_id else 0
        return Response({"count": count})


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        notification = Notification.objects.filter(
            pk=pk,
            company_id=request.user.company_id,
            recipient=request.user,
        ).first()
        if not notification:
            return Response({"detail": "Notification is not available."}, status=status.HTTP_404_NOT_FOUND)
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at"])
        return Response(NotificationSerializer(notification).data)


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(
            company_id=request.user.company_id,
            recipient=request.user,
            is_read=False,
        ).update(is_read=True, read_at=timezone.now())
        return Response(status=status.HTTP_204_NO_CONTENT)
