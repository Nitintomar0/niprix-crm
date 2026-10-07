import csv
import io
import zipfile
from datetime import date
from xml.etree import ElementTree

from django.db import IntegrityError
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from leads.services import normalize_phone
from leads.models import Lead
from .models import RawLead
from .serializers import DistributionRequestSerializer, PreviewRowsSerializer, RawLeadSerializer
from .services import allocation_for, distribute, persist_preview_rows, raw_company_for, raw_queryset, validate_preview_rows


class RawLeadPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class RawLeadListCreateView(generics.ListCreateAPIView):
    serializer_class = RawLeadSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = RawLeadPagination

    def get_queryset(self):
        queryset = raw_queryset(self.request.user)
        params = self.request.query_params
        if search := params.get("search", "").strip():
            queryset = queryset.filter(Q(name__icontains=search) | Q(phone__icontains=search) | Q(email__icontains=search) | Q(preferred_location__icontains=search))
        for parameter, field in (("location", "preferred_location"), ("property_type", "property_type"), ("source", "source")):
            if value := params.get(parameter, "").strip():
                queryset = queryset.filter(**{f"{field}__icontains": value} if parameter != "source" else {field: value})
        if value := params.get("date_from"):
            try:
                queryset = queryset.filter(created_at__date__gte=date.fromisoformat(value))
            except ValueError:
                raise ValidationError({"date_from": "Use ISO date format YYYY-MM-DD."})
        if value := params.get("date_to"):
            try:
                queryset = queryset.filter(created_at__date__lte=date.fromisoformat(value))
            except ValueError:
                raise ValidationError({"date_to": "Use ISO date format YYYY-MM-DD."})
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            self.perform_create(serializer)
        except ValidationError as exc:
            detail = exc.detail
            return Response(
                {
                    "detail": detail,
                    "errors": detail if isinstance(detail, dict) else {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        headers = self.get_success_headers(serializer.data)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )


    def perform_create(self, serializer):
        company = raw_company_for(self.request.user)

        normalized = normalize_phone(
            serializer.validated_data["phone"]
        )

        if not normalized:
            raise ValidationError({
                "phone": "Enter a valid phone number."
            })

        if RawLead.objects.filter(
        company=company,
        normalized_phone=normalized,
        ).exists():
            raise ValidationError({
                "phone": "A raw lead with this phone already exists."
            })

        if Lead.objects.filter(
        company=company,
        normalized_phone=normalized,
        ).exists():
            raise ValidationError({
                "phone": "A normal CRM lead with this phone already exists."
            })

        try:
            serializer.save(
                company=company,
                created_by=self.request.user,
                normalized_phone=normalized,
            )
        except IntegrityError:
            raise ValidationError({
                "phone": "A raw lead with this phone already exists."
            })

class RawLeadDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RawLeadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return raw_queryset(self.request.user)

    def perform_update(self, serializer):
        company = raw_company_for(self.request.user)
        phone = serializer.validated_data.get("phone", serializer.instance.phone)
        normalized = __import__("leads.services", fromlist=["normalize_phone"]).normalize_phone(phone)
        duplicate = RawLead.objects.filter(company=company, normalized_phone=normalized).exclude(pk=serializer.instance.pk).exists()
        from leads.models import Lead
        if duplicate or Lead.objects.filter(company=company, normalized_phone=normalized).exists():
            raise ValidationError({"phone": "This phone number already exists in Raw Data or CRM Leads."})
        serializer.save(normalized_phone=normalized)


class RawDataSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = raw_queryset(request.user)
        return Response({"total": queryset.count(), "available": queryset.count()})


def _canonical_header(value):
    cleaned = "".join(character.lower() if character.isalnum() else "_" for character in str(value)).strip("_")
    aliases = {
        "full_name": "name", "customer_name": "name", "mobile": "phone", "mobile_number": "phone", "phone_number": "phone",
        "city": "preferred_location", "location": "preferred_location", "property": "property_type", "property_type": "property_type",
        "requirement": "requirement_notes", "notes": "requirement_notes", "budget_min": "budget_minimum", "budget_max": "budget_maximum",
    }
    return aliases.get(cleaned, cleaned)

def _clean_import_phone(value):
    """
    Excel/CSV phone values ko normal phone string mein convert karta hai.

    Example:
    9.818940829E9 -> 9818940829
    9818940829    -> 9818940829
    "9818940829"  -> 9818940829
    """
    if value is None:
        return ""

    text = str(value).strip()

    if not text:
        return ""

    try:
        from decimal import Decimal, InvalidOperation

        number = Decimal(text)

        # Scientific notation / numeric Excel value
        if number == number.to_integral_value():
            return format(number, "f").split(".")[0]

    except (InvalidOperation, ValueError):
        pass

    return text

def _xlsx_rows(uploaded):
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    rel_namespace = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    archive = zipfile.ZipFile(uploaded)
    shared = []
    if "xl/sharedStrings.xml" in archive.namelist():
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
        shared = ["".join(node.itertext()) for node in root.findall(f"{namespace}si")]
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    first = workbook.find(f".//{namespace}sheet")
    if first is None:
        return []
    rel_id = first.attrib.get(rel_namespace)
    rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    target = next((node.attrib["Target"] for node in rels if node.attrib.get("Id") == rel_id), None)
    if not target:
        return []
    path = "xl/" + target.lstrip("/")
    root = ElementTree.fromstring(archive.read(path))
    rows = []
    for row in root.findall(f".//{namespace}sheetData/{namespace}row"):
        values = []
        for cell in row.findall(f"{namespace}c"):
            reference = cell.attrib.get("r", "A1")
            letters = "".join(character for character in reference if character.isalpha())
            position = 0
            for character in letters:
                position = position * 26 + ord(character.upper()) - 64
            position = max(position - 1, 0)
            if len(values) <= position:
                values.extend([""] * (position + 1 - len(values)))
            value = cell.findtext(f"{namespace}v", "")

            if cell.attrib.get("t") == "s" and value:
                value = _clean_import_phone(shared[int(value)])
            elif cell.attrib.get("t") == "inlineStr":
                value = "".join(cell.itertext())

            values[position] = value
        rows.append(values)
    return rows


class RawDataPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        raw_company_for(request.user)
        if "file" in request.FILES:
            uploaded = request.FILES["file"]
            extension = uploaded.name.rsplit(".", 1)[-1].lower() if "." in uploaded.name else ""
            if uploaded.size > 10 * 1024 * 1024:
                raise ValidationError({"file": "File must not exceed 10 MB."})
            try:
                if extension == "csv":
                    values = list(csv.reader(io.TextIOWrapper(uploaded.file, encoding="utf-8-sig")))
                elif extension == "xlsx":
                    values = _xlsx_rows(uploaded)
                else:
                    raise ValidationError({"file": "Upload a CSV or XLSX file."})
            except (UnicodeDecodeError, zipfile.BadZipFile, ElementTree.ParseError, IndexError):
                raise ValidationError({"file": "The uploaded file could not be read."})
            if not values:
                raise ValidationError({"file": "The uploaded file has no rows."})
            headers = [_canonical_header(value) for value in values[0]]
            supported = set(__import__("raw_data.serializers", fromlist=["RAW_FIELDS"]).RAW_FIELDS)
            if not set(headers) & supported:
                raise ValidationError({"file": "File contains no supported lead columns."})
            rows = []

            for row in values[1:]:
                if not any(str(value).strip() for value in row):
                    continue

                parsed_row = {}

                for index, header in enumerate(headers):
                    if header not in supported:
                        continue

                    value = row[index] if index < len(row) else ""

        # Excel often stores phone numbers as scientific notation.
                    if header == "phone":
                        value = _clean_import_phone(value)

                    parsed_row[header] = value

                rows.append(parsed_row)
        else:
            serializer = PreviewRowsSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            rows = serializer.validated_data["rows"]
        preview = validate_preview_rows(request.user, rows)
        valid = sum(row["valid"] for row in preview)
        duplicates = sum(any("Duplicate" in error or "already exists" in error for error in row["errors"]) for row in preview)
        return Response({"rows": preview, "summary": {"total": len(preview), "valid": valid, "invalid": len(preview) - valid, "duplicates": duplicates}})


class RawDataSavePreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PreviewRowsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created, preview = persist_preview_rows(request.user, serializer.validated_data["rows"])
        return Response({"created": len(created), "rows": RawLeadSerializer(created, many=True).data, "preview": preview}, status=status.HTTP_201_CREATED)


class RawDataEligibleEmployeesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .services import eligible_employees
        return Response([{"id": item.pk, "username": item.user.username, "employee_code": item.employee_code, "branch": item.branch_id} for item in eligible_employees(request.user)])


class RawDataDistributionPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DistributionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_leads, allocations = allocation_for(request.user, serializer.validated_data)
        return Response({
            "raw_lead_ids": [row.pk for row in raw_leads], "total": len(raw_leads), "mode": serializer.validated_data["mode"],
            "allocations": [{"employee_id": employee.pk, "employee_name": employee.user.get_full_name() or employee.user.username, "count": count} for employee, count in allocations],
        })


class RawDataDistributionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DistributionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        leads, allocations = distribute(request.user, serializer.validated_data)
        return Response({"distributed": len(leads), "lead_ids": [lead.pk for lead in leads], "allocations": [{"employee_id": employee.pk, "count": count} for employee, count in allocations]})
