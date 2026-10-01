import json

from rest_framework import generics, status
from rest_framework.exceptions import NotAuthenticated, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from leads.views import LeadPagination

from .models import IntegrationConfiguration, IntegrationEvent
from .serializers import IntegrationConfigurationSerializer, IntegrationEventSerializer
from .services import InvalidWebhook, process_webhook, verify_signature


def _is_admin(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.role == "CEO"))


class IntegrationConfigurationListCreateView(generics.ListCreateAPIView):
    serializer_class = IntegrationConfigurationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LeadPagination

    def initial(self, request, *args, **kwargs):
        if not _is_admin(request.user):
            raise PermissionDenied("Only CEO users can manage integrations.")
        return super().initial(request, *args, **kwargs)

    def get_queryset(self):
        return IntegrationConfiguration.objects.filter(company=self.request.user.company).select_related("branch").order_by("provider", "id")


class IntegrationConfigurationDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = IntegrationConfigurationSerializer
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        if not _is_admin(request.user):
            raise PermissionDenied("Only CEO users can manage integrations.")
        return super().initial(request, *args, **kwargs)

    def get_queryset(self):
        return IntegrationConfiguration.objects.filter(company=self.request.user.company).select_related("branch")


class IntegrationEventListView(generics.ListAPIView):
    serializer_class = IntegrationEventSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LeadPagination

    def initial(self, request, *args, **kwargs):
        if not _is_admin(request.user):
            raise PermissionDenied("Only CEO users can inspect integration events.")
        return super().initial(request, *args, **kwargs)

    def get_queryset(self):
        queryset = IntegrationEvent.objects.select_related("configuration", "lead").filter(company=self.request.user.company)
        provider = self.request.query_params.get("provider")
        if provider:
            queryset = queryset.filter(provider=provider)
        return queryset


class WebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    provider = ""

    def post(self, request):
        raw_body = request.body
        header = "X-Niprix-Signature-256" if self.provider == "WEBSITE" else "X-Hub-Signature-256"
        try:
            verify_signature(provider=self.provider, raw_body=raw_body, signature=request.headers.get(header, ""))
            payload = json.loads(raw_body.decode("utf-8"))
            result = process_webhook(provider=self.provider, raw_body=raw_body, payload=payload)
        except json.JSONDecodeError:
            return Response({"detail": "Webhook body must be valid JSON."}, status=status.HTTP_400_BAD_REQUEST)
        except InvalidWebhook as error:
            return Response({"detail": str(error)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as error:
            return Response(error.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            # Detailed safe errors are persisted on the event; do not return internals.
            return Response({"detail": "Webhook processing failed."}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        return Response({"status": result.event.status, "duplicate": result.duplicate}, status=status.HTTP_200_OK)


class WhatsAppWebhookView(WebhookView):
    provider = "WHATSAPP"


class FacebookWebhookView(WebhookView):
    provider = "FACEBOOK"


class InstagramWebhookView(WebhookView):
    provider = "INSTAGRAM"


class WebsiteIntakeView(WebhookView):
    provider = "WEBSITE"
