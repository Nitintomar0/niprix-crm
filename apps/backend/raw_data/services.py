from collections import Counter
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied, ValidationError

from core.audit import log_action
from core.notifications import notify_company_roles
from leads.models import Lead
from leads.services import company_for, create_or_enrich_lead, normalize_phone
from organizations.models import EmployeeProfile

from .models import RawLead
from .serializers import RAW_FIELDS


def raw_company_for(user):
    company = company_for(user)
    if not (user.is_superuser or user.role == "CEO"):
        raise PermissionDenied("Raw Data is available only to the CEO.")
    return company


def raw_queryset(user):
    return RawLead.objects.select_related("created_by").filter(company=raw_company_for(user))


def eligible_employees(user):
    company = raw_company_for(user)
    return EmployeeProfile.objects.select_related("user", "branch").filter(
        branch__company=company, user__company=company, user__role="EMPLOYEE",
        is_active=True, user__is_active=True, can_receive_leads=True,
    ).order_by("pk")


def _clean_value(row, field):
    value = row.get(field, "")
    return "" if value is None else str(value).strip()


def validate_preview_rows(user, rows):
    """Return stateless, editable validation output; this endpoint never writes rows."""
    company = raw_company_for(user)
    normalized_rows = []
    phones = []
    for index, supplied in enumerate(rows):
        row = {field: _clean_value(supplied, field) for field in RAW_FIELDS}
        row["source"] = row["source"].upper() or Lead.Source.MANUAL
        normalized = normalize_phone(row["phone"])
        row["normalized_phone"] = normalized
        row["row_number"] = index + 1
        row["errors"] = []
        if not normalized:
            row["errors"].append("Phone number is invalid.")
        if row["email"]:
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError as DjangoValidationError
            try:
                validate_email(row["email"])
            except DjangoValidationError:
                row["errors"].append("Email address is invalid.")
        if row["source"] not in Lead.Source.values:
            row["errors"].append("Source is unsupported.")
        try:
            low = Decimal(row["budget_minimum"]) if row["budget_minimum"] else None
            high = Decimal(row["budget_maximum"]) if row["budget_maximum"] else None
            if low is not None and high is not None and low > high:
                row["errors"].append("Budget maximum must be at least budget minimum.")
        except InvalidOperation:
            row["errors"].append("Budget values must be numbers.")
        normalized_rows.append(row)
        if normalized:
            phones.append(normalized)
    in_file = Counter(phones)
    existing_raw = set(RawLead.objects.filter(company=company, normalized_phone__in=set(phones)).values_list("normalized_phone", flat=True))
    existing_leads = set(Lead.objects.filter(company=company, normalized_phone__in=set(phones)).values_list("normalized_phone", flat=True))
    for row in normalized_rows:
        phone = row["normalized_phone"]
        if phone and in_file[phone] > 1:
            row["errors"].append("Duplicate phone number in this file.")
        if phone in existing_raw:
            row["errors"].append("Duplicate raw lead already exists.")
        if phone in existing_leads:
            row["errors"].append("A normal CRM lead already exists with this phone.")
        row["valid"] = not row["errors"]
    return normalized_rows


def persist_preview_rows(user, rows):
    validated = validate_preview_rows(user, rows)
    approved = [row for row in validated if row["valid"]]
    if not approved:
        raise ValidationError({"rows": "No valid, unique rows are available to save."})
    company = raw_company_for(user)
    with transaction.atomic():
        # Re-run validation while the unique database constraint provides a final race-safe guard.
        created = []
        for row in approved:
            payload = {field: row[field] for field in RAW_FIELDS}
            payload["budget_minimum"] = payload["budget_minimum"] or None
            payload["budget_maximum"] = payload["budget_maximum"] or None
            created.append(RawLead.objects.create(
                company=company, created_by=user, normalized_phone=row["normalized_phone"], **payload,
            ))
        log_action(actor=user, company=company, action="raw_lead.imported", target=created[0], metadata={"count": len(created)})
    return created, validated


def _raw_leads_for_request(user, data, lock=False):
    company = raw_company_for(user)
    query = RawLead.objects.filter(company=company)
    if lock:
        query = query.select_for_update()
    ids = data.get("raw_lead_ids")
    if ids:
        if len(set(ids)) != len(ids):
            raise ValidationError({"raw_lead_ids": "A raw lead may only be selected once."})
        found = list(query.filter(pk__in=ids).order_by("created_at", "pk"))
        if len(found) != len(ids):
            raise ValidationError({"raw_lead_ids": "One or more selected raw leads are no longer available."})
        return found
    quantity = data["quantity"]
    found = list(query.order_by("created_at", "pk")[:quantity])
    if len(found) != quantity:
        raise ValidationError({"quantity": "Requested quantity exceeds available raw leads."})
    return found


def allocation_for(user, data, lock=False):
    people = list(eligible_employees(user).filter(pk__in=data["employee_ids"]))
    if len(people) != len(set(data["employee_ids"])):
        raise ValidationError({"employee_ids": "Every employee must be an active eligible employee in your company."})
    people_by_id = {person.pk: person for person in people}
    # Preserve CEO's supplied employee order for a deterministic fair remainder.
    people = [people_by_id[pk] for pk in data["employee_ids"]]
    raw_leads = _raw_leads_for_request(user, data, lock=lock)
    total = len(raw_leads)
    if data["mode"] == "SPECIFIC":
        quantities = [total]
    elif data["mode"] == "EQUAL":
        base, remainder = divmod(total, len(people))
        quantities = [base + (1 if index < remainder else 0) for index in range(len(people))]
    else:
        supplied = data["allocations"]
        unexpected = set(supplied) - {str(person.pk) for person in people}
        if unexpected:
            raise ValidationError({"allocations": "Allocation contains an unselected employee."})
        quantities = [supplied.get(str(person.pk), supplied.get(person.pk, 0)) for person in people]
        if sum(quantities) != total:
            raise ValidationError({"allocations": "Distribution total must exactly match the selected raw leads."})
    return raw_leads, list(zip(people, quantities))


def distribute(user, data):
    company = raw_company_for(user)
    with transaction.atomic():
        raw_leads, allocations = allocation_for(user, data, lock=True)
        # A late normal-lead collision must abort, rather than wrongly reassign an existing lead.
        collisions = Lead.objects.select_for_update().filter(
            company=company, normalized_phone__in=[row.normalized_phone for row in raw_leads],
        )
        if collisions.exists():
            raise ValidationError({"raw_lead_ids": "A selected raw lead now duplicates an existing CRM lead. Refresh and review it."})
        index = 0
        created = []
        for employee, count in allocations:
            for raw in raw_leads[index:index + count]:
                payload = {field: getattr(raw, field) for field in RAW_FIELDS}
                payload.update({"assigned_to": employee, "branch": employee.branch})
                mutation = create_or_enrich_lead(actor=user, company=company, data=payload)
                if not mutation.created:
                    raise ValidationError({"raw_lead_ids": "A selected raw lead was already created as a CRM lead. Refresh and try again."})
                created.append(mutation.lead)
            index += count
        RawLead.objects.filter(pk__in=[raw.pk for raw in raw_leads], company=company).delete()
        log_action(actor=user, company=company, action="raw_lead.distributed", target=created[0], metadata={
            "raw_lead_count": len(raw_leads),
            "allocations": [{"employee_id": employee.pk, "count": count} for employee, count in allocations],
        })
        notify_company_roles(
            company=company,
            roles=["CEO"],
            notification_type="RAW_DATA",
            title="Raw Data distributed",
            body=f"{len(created)} raw lead{'s' if len(created) != 1 else ''} moved into the CRM pipeline.",
            href="/raw-data",
            metadata={
                "lead_ids": [lead.pk for lead in created],
                "allocations": [{"employee_id": employee.pk, "count": count} for employee, count in allocations],
            },
        )
    return created, allocations
