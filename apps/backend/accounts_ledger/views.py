from django.db.models import Q
from django.http import HttpResponse
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.renderers import BaseRenderer, JSONRenderer

from core.audit import log_action

from .models import CustomerLedger, IssuedReceipt
from .pdf import build_receipt_pdf
from .serializers import CancellationSerializer, CustomerLedgerSerializer, IssueReceiptSerializer, ReceiptSerializer
from .services import cancel_receipt, issue_receipt


class IsCEOOrSuperuser(BasePermission):
    message = "Only CEO or Super Admin users can access Accounts."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_active and request.user.company_id and (request.user.is_superuser or request.user.role == "CEO"))


def ledger_queryset(user):
    if not user.company_id:
        raise PermissionDenied("An active company account is required.")
    return CustomerLedger.objects.filter(company_id=user.company_id).prefetch_related("payments__receipt", "receipts")


class LedgerPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class CustomerLedgerListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsCEOOrSuperuser]
    serializer_class = CustomerLedgerSerializer
    pagination_class = LedgerPagination

    def get_queryset(self):
        queryset = ledger_queryset(self.request.user)
        if search := self.request.query_params.get("search", "").strip():
            queryset = queryset.filter(Q(name__icontains=search) | Q(mobile__icontains=search) | Q(project__icontains=search) | Q(plot_number__icontains=search))
        if status_filter := self.request.query_params.get("status", "").strip():
            if status_filter not in CustomerLedger.Status.values:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({"status": "Contains an unsupported value."})
            queryset = queryset.filter(status=status_filter)
        return queryset

    def perform_create(self, serializer):
        customer = serializer.save(company_id=self.request.user.company_id, created_by=self.request.user, updated_by=self.request.user)
        log_action(actor=self.request.user, company=customer.company, action="accounts.customer_created", target=customer)


class CustomerLedgerDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, IsCEOOrSuperuser]
    serializer_class = CustomerLedgerSerializer

    def get_queryset(self):
        return ledger_queryset(self.request.user)

    def perform_update(self, serializer):
        customer = serializer.save(updated_by=self.request.user)
        log_action(actor=self.request.user, company=customer.company, action="accounts.customer_updated", target=customer)


class IssueReceiptView(APIView):
    permission_classes = [IsAuthenticated, IsCEOOrSuperuser]

    def post(self, request, customer_id):
        serializer = IssueReceiptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        receipt = issue_receipt(customer_id=customer_id, company_id=request.user.company_id, actor=request.user, data=serializer.validated_data)
        return Response(ReceiptSerializer(receipt).data, status=status.HTTP_201_CREATED)

class PDFRenderer(BaseRenderer):
    media_type = "application/pdf"
    format = "pdf"
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data
    

class ReceiptPDFView(APIView):
    renderer_classes = [PDFRenderer]
    permission_classes = [IsAuthenticated, IsCEOOrSuperuser]

    def get(self, request, pk):
        receipt = IssuedReceipt.objects.filter(company_id=request.user.company_id, pk=pk).first()
        if not receipt:
            from django.http import Http404
            raise Http404
        response = HttpResponse(build_receipt_pdf(receipt), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="paramshiv-receipt-{receipt.serial_number}.pdf"'
        response["Cache-Control"] = "private, no-store"
        return response


class ReceiptCancelView(APIView):
    permission_classes = [IsAuthenticated, IsCEOOrSuperuser]

    def post(self, request, pk):
        serializer = CancellationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        receipt = IssuedReceipt.objects.filter(company_id=request.user.company_id, pk=pk).first()
        if not receipt:
            from django.http import Http404
            raise Http404
        receipt = cancel_receipt(receipt=receipt, actor=request.user, reason=serializer.validated_data["reason"])
        return Response(ReceiptSerializer(receipt).data)
