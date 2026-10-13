from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.renderers import BaseRenderer

from core.audit import log_action
from core.notifications import notify_company_roles
from .models import InventoryItem
from .pdf import build_inventory_pdf
from .serializers import InventoryBulkCreateSerializer, InventoryItemSerializer


def is_ceo(user):
    return user.is_superuser or user.role == "CEO"


def inventory_queryset(user):
    if not user.is_authenticated or not user.is_active or not user.company_id:
        raise PermissionDenied("An active company account is required.")
    return InventoryItem.objects.filter(company_id=user.company_id, archived_at__isnull=True)


def can_write(user):
    if user.is_superuser or user.role in ("CEO", "MANAGER"):
        return
    raise PermissionDenied("Only CEOs and managers can manage inventory.")


class InventoryPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class InventoryListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = InventoryPagination

    def get_serializer_class(self):
        return InventoryItemSerializer

    def get_queryset(self):
        params = self.request.query_params
        queryset = inventory_queryset(self.request.user)
        if params.get("search"):
            term = params["search"].strip()
            queryset = queryset.filter(Q(project__icontains=term) | Q(unit_number__icontains=term) | Q(property_type__icontains=term) | Q(floor__icontains=term))
        for key, field, valid in (("status", "status", InventoryItem.Status.values),):
            if params.get(key):
                if params[key] not in valid:
                    raise ValidationError({key: "Contains an unsupported value."})
                queryset = queryset.filter(**{field: params[key]})
        for key in ("project", "property_type", "floor"):
            if params.get(key):
                queryset = queryset.filter(**{f"{key}__icontains": params[key].strip()})
        if params.get("booking_date"):
            try:
                queryset = queryset.filter(booking_date=params["booking_date"])
            except ValueError:
                raise ValidationError({"booking_date": "Use ISO date format YYYY-MM-DD."})
        return queryset

    def perform_create(self, serializer):
        can_write(self.request.user)
        if not is_ceo(self.request.user) and "landing" in self.request.data:
            raise PermissionDenied("Only CEOs can set landing.")
        item = serializer.save(company_id=self.request.user.company_id, created_by=self.request.user)
        log_action(actor=self.request.user, company=item.company, action="inventory.created", target=item)


class InventoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = InventoryItemSerializer

    def get_queryset(self):
        return inventory_queryset(self.request.user)

    def perform_update(self, serializer):
        can_write(self.request.user)
        if not is_ceo(self.request.user) and "landing" in self.request.data:
            raise PermissionDenied("Only CEOs can update landing.")
        was_booked = serializer.instance.status in {InventoryItem.Status.BOOKED, InventoryItem.Status.SOLD}
        item = serializer.save()
        log_action(actor=self.request.user, company=item.company, action="inventory.updated", target=item)
        if not was_booked and item.status in {InventoryItem.Status.BOOKED, InventoryItem.Status.SOLD}:
            notify_company_roles(
                company=item.company,
                roles=["CEO"],
                notification_type="INVENTORY",
                title="Inventory unit booked",
                body=f"{item.project} · Unit {item.unit_number} is now {item.get_status_display().lower()}.",
                href="/inventory",
                metadata={"inventory_id": item.pk, "status": item.status},
            )

    def perform_destroy(self, instance):
        can_write(self.request.user)
        instance.archived_at = timezone.now()
        instance.save(update_fields=["archived_at", "updated_at"])
        log_action(actor=self.request.user, company=instance.company, action="inventory.archived", target=instance)


class InventoryBulkCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        can_write(request.user)
        if not is_ceo(request.user):
            for item in request.data.get("items", []):
                if "landing" in item:
                    raise PermissionDenied("Only CEOs can set landing.")
        serializer = InventoryBulkCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                items = [InventoryItem(company_id=request.user.company_id, created_by=request.user, **data) for data in serializer.validated_data["items"]]
                InventoryItem.objects.bulk_create(items)
        except IntegrityError:
            raise ValidationError({"items": "A project already contains one of these unit numbers."})
        for item in items:
            log_action(actor=request.user, company=item.company, action="inventory.created", target=item, metadata={"bulk": True})
        return Response(InventoryItemSerializer(items, many=True, context={"request": request}).data, status=status.HTTP_201_CREATED)


class InventorySummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = inventory_queryset(request.user)
        aggregates = {
            "total": Count("id"),
            "available": Count("id", filter=Q(status=InventoryItem.Status.AVAILABLE)),
            "hold": Count("id", filter=Q(status=InventoryItem.Status.HOLD)),
            "booked": Count("id", filter=Q(status=InventoryItem.Status.BOOKED)),
            "sold": Count("id", filter=Q(status=InventoryItem.Status.SOLD)),
        }
        if is_ceo(request.user):
            aggregates["landing_total"] = Sum("landing")
        counts = queryset.aggregate(**aggregates)
        result = {key: counts[key] for key in ("total", "available", "hold", "booked", "sold")}
        if is_ceo(request.user):
            result["landing_total"] = str(counts["landing_total"] or 0)
        return Response(result)



class PDFRenderer(BaseRenderer):
    media_type = "application/pdf"
    format = "pdf"
    charset = None
    render_style = "binary"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data

class InventoryPDFExportView(APIView):
    """CEO-only complete-inventory export. Pagination and UI filters never apply."""

    permission_classes = [IsAuthenticated]
    renderer_classes = [PDFRenderer]

    def get(self, request):
        if not is_ceo(request.user):
            raise PermissionDenied("Only CEOs can export the complete inventory report.")

        # Use the tenant-scoped base queryset directly: this is intentionally
        # not the paginated list view and therefore cannot omit later pages.
        records = inventory_queryset(request.user).values_list(
            "project",
            "unit_number",
            "property_type",
            "size_sqft",
            "floor",
            "basic_price",
            "status",
            "landing",
            "booking_date",
        )
        pdf = build_inventory_pdf(records)
        timestamp = timezone.localtime(timezone.now()).strftime("%Y%m%d-%H%M%S")
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="niprix-inventory-{timestamp}.pdf"'
        response["Cache-Control"] = "no-store, private"
        return response
