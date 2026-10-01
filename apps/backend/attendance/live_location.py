"""Short-lived, tenant-scoped employee location state and live relay."""

from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.cache import cache
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from .models import AttendanceRecord


class LiveLocationBackendUnavailable(APIException):
    status_code = 503
    default_detail = "Live location service is temporarily unavailable."
    default_code = "live_location_unavailable"


def location_key(company_id: int, employee_id: int) -> str:
    return f"attendance:live-location:{company_id}:{employee_id}"


def location_group(company_id: int, employee_id: int) -> str:
    return f"live_location_{company_id}_{employee_id}"


def _active_record(profile):
    return AttendanceRecord.objects.filter(
        company=profile.branch.company,
        employee=profile,
        attendance_date=timezone.localdate(),
        check_in_at__isnull=False,
        check_out_at__isnull=True,
    ).exists()


def _broadcast(company_id: int, employee_id: int, state: dict) -> None:
    """Relay only to the private, company-and-employee-specific group."""
    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(
            location_group(company_id, employee_id),
            {"type": "location.update", "state": state},
        )


def unavailable_state(reason: str = "offline") -> dict:
    return {"status": "unavailable", "reason": reason}


def get_live_location(*, company_id: int, employee_id: int) -> dict:
    try:
        state = cache.get(location_key(company_id, employee_id))
    except Exception as exc:
        raise LiveLocationBackendUnavailable() from exc
    if not state:
        return unavailable_state()
    updated_at = parse_datetime(state.get("updated_at", ""))
    if not updated_at or (timezone.now() - updated_at).total_seconds() > settings.LIVE_LOCATION_STALE_SECONDS:
        try:
            cache.delete(location_key(company_id, employee_id))
        except Exception as exc:
            raise LiveLocationBackendUnavailable() from exc
        return unavailable_state("stale")
    return state


def _save_state(*, key: str, company_id: int, employee_id: int, state: dict) -> dict:
    try:
        cache.set(key, state, timeout=settings.LIVE_LOCATION_TTL_SECONDS)
        _broadcast(company_id, employee_id, state)
    except Exception as exc:
        raise LiveLocationBackendUnavailable() from exc
    return state


def submit_live_location(*, profile, latitude, longitude, accuracy) -> dict:
    """Validate a sender's own active attendance session and replace its state."""
    if not profile.is_active or not profile.user.is_active:
        raise PermissionDenied("An active employee profile is required.")
    if not _active_record(profile):
        raise ValidationError({"detail": "Live location is available only during an active attendance session."})

    try:
        latitude, longitude, accuracy = float(latitude), float(longitude), float(accuracy)
    except (TypeError, ValueError):
        raise ValidationError({"detail": "Latitude, longitude, and accuracy must be valid numbers."})
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180 or accuracy < 0 or accuracy > 100_000:
        raise ValidationError({"detail": "Location coordinates or accuracy are outside the permitted range."})

    company_id, employee_id = profile.branch.company_id, profile.pk
    key = location_key(company_id, employee_id)
    try:
        previous = cache.get(key)
    except Exception as exc:
        raise LiveLocationBackendUnavailable() from exc
    previous_timestamp = parse_datetime(previous.get("updated_at", "")) if previous else None
    if previous_timestamp and (timezone.now() - previous_timestamp).total_seconds() < settings.LIVE_LOCATION_MIN_UPDATE_SECONDS:
        # A browser sender may be modified, but it still cannot turn this into
        # a high-frequency Redis or WebSocket stream.
        return previous
    state = {
        "status": "live",
        "latitude": latitude,
        "longitude": longitude,
        "accuracy": round(accuracy, 1),
        # Use the server clock; a browser-provided timestamp is not trusted.
        "updated_at": timezone.now().isoformat(),
        "attendance": "checked_in",
    }
    return _save_state(key=key, company_id=company_id, employee_id=employee_id, state=state)


def report_live_location_status(*, profile, reason: str) -> dict:
    """Record a temporary, coordinate-free browser GPS state for the CEO."""
    if not _active_record(profile):
        raise ValidationError({"detail": "Live location is available only during an active attendance session."})
    allowed_reasons = {"permission_denied", "position_unavailable", "timeout", "missing_coordinates"}
    if reason not in allowed_reasons:
        raise ValidationError({"status": "Unsupported live location status."})
    company_id, employee_id = profile.branch.company_id, profile.pk
    state = {"status": "unavailable", "reason": reason, "updated_at": timezone.now().isoformat(), "attendance": "checked_in"}
    return _save_state(key=location_key(company_id, employee_id), company_id=company_id, employee_id=employee_id, state=state)


def clear_live_location(*, profile) -> None:
    """Remove GPS data on checkout and explicitly notify authorized viewers."""
    company_id, employee_id = profile.branch.company_id, profile.pk
    try:
        cache.delete(location_key(company_id, employee_id))
        _broadcast(company_id, employee_id, unavailable_state())
    except Exception as exc:
        raise LiveLocationBackendUnavailable() from exc
