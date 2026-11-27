import re
from django.db.models import Q
from django.utils import timezone

BLOCKED_MESSAGE = (
    "You have been blocked by the administrator and cannot register or log in "
    "with this email or mobile number."
)

GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}


def normalize_email(email):
    """Return lowercased, trimmed email or empty string."""
    return str(email or "").strip().lower()


def canonicalize_email(email):
    """
    Canonicalize email for duplicate/evasion detection.
    For Gmail/Googlemail, strip dots and +aliases in the local part and normalize domain to gmail.com.
    """
    norm = normalize_email(email)
    if "@" not in norm:
        return norm
    local, domain = norm.rsplit("@", 1)
    if domain in GMAIL_DOMAINS:
        local = local.split("+", 1)[0].replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}"


def normalize_phone(phone):
    """
    Return (digits, last10) for a phone/mobile number.
    Numbers shorter than 7 digits are treated as empty to avoid false positives.
    """
    digits = re.sub(r"\D", "", str(phone or ""))
    if len(digits) < 7:
        return "", ""
    last10 = digits[-10:] if len(digits) >= 10 else ""
    return digits, last10


def format_blocked_message(reason=None):
    reason_text = str(reason or "").strip()
    if reason_text:
        return f"{BLOCKED_MESSAGE} Reason: {reason_text}"
    return BLOCKED_MESSAGE


def collect_user_phones(user):
    """Collect distinct non-empty phone numbers from User and UserProfile."""
    candidates = []
    if getattr(user, "phone_number", None):
        candidates.append(user.phone_number)
    try:
        from userProfile.models import UserProfile
        profile_mobile = (
            UserProfile.objects.filter(user=user)
            .values_list("mobile_number", flat=True)
            .first()
        )
        if profile_mobile:
            candidates.append(profile_mobile)
    except Exception:
        pass

    seen = set()
    normalized_list = []
    for raw in candidates:
        digits, last10 = normalize_phone(raw)
        if digits and digits not in seen:
            seen.add(digits)
            normalized_list.append((digits, last10))
    return normalized_list


def sync_block_record_for_user(user, reason=""):
    """
    Ensure active BlockedContact record(s) exist for a blocked/inactive user,
    capturing their email (and canonical Gmail) as well as all known mobile numbers.
    """
    from .models import BlockedContact

    norm_email = normalize_email(getattr(user, "email", ""))
    canon_email = canonicalize_email(norm_email) if norm_email else ""
    phones = collect_user_phones(user)
    effective_reason = str(reason or getattr(user, "blocked_reason", "") or "").strip()

    if not phones:
        phones = [("", "")]

    for idx, (digits, last10) in enumerate(phones):
        email_for_row = norm_email if idx == 0 else ""
        canon_for_row = canon_email if idx == 0 else ""

        existing = None
        if email_for_row:
            existing = BlockedContact.objects.filter(
                user=user, email=email_for_row
            ).first()
        elif digits:
            existing = BlockedContact.objects.filter(
                user=user, phone_number=digits
            ).first()

        if existing:
            existing.canonical_email = canon_for_row or existing.canonical_email
            if digits:
                existing.phone_number = digits
                existing.phone_last10 = last10
            if effective_reason:
                existing.reason = effective_reason
            existing.is_active = True
            existing.save()
        else:
            BlockedContact.objects.create(
                user=user,
                email=email_for_row or None,
                canonical_email=canon_for_row or None,
                phone_number=digits or None,
                phone_last10=last10 or None,
                reason=effective_reason,
                is_active=True,
            )


def deactivate_block_records_for_user(user):
    """Deactivate BlockedContact records associated with an unblocked user."""
    from .models import BlockedContact

    q = Q(user=user)
    norm_email = normalize_email(getattr(user, "email", ""))
    if norm_email:
        q |= Q(email=norm_email)
    BlockedContact.objects.filter(q, is_active=True).update(is_active=False)


def block_user(user, reason=""):
    """Block a user account and persist their email and mobile number(s)."""
    user.is_blocked = True
    user.is_active = False
    if reason:
        user.blocked_reason = reason
    if not user.blocked_at:
        user.blocked_at = timezone.now()
    user.save(update_fields=["is_blocked", "is_active", "blocked_reason", "blocked_at"])
    sync_block_record_for_user(user, reason=user.blocked_reason or reason)


def unblock_user(user):
    """Unblock a user account and deactivate its BlockedContact records."""
    user.is_blocked = False
    user.is_active = True
    user.blocked_reason = ""
    user.blocked_at = None
    user.save(update_fields=["is_blocked", "is_active", "blocked_reason", "blocked_at"])
    deactivate_block_records_for_user(user)


def _find_blocked_user_fallback(norm_email, canon_email, digits, last10):
    """Fallback check directly on User/UserProfile in case is_active=False was set via bulk update."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    blocked_users = User.objects.filter(Q(is_blocked=True) | Q(is_active=False))

    if norm_email:
        user_match = blocked_users.filter(email__iexact=norm_email).first()
        if user_match:
            return user_match
        if canon_email and canon_email.endswith("@gmail.com"):
            for candidate in blocked_users.filter(
                Q(email__iendswith="@gmail.com") | Q(email__iendswith="@googlemail.com")
            ).only("id", "email", "blocked_reason"):
                if canonicalize_email(candidate.email) == canon_email:
                    return candidate

    if digits:
        for candidate in blocked_users.filter(
            Q(phone_number__isnull=False) | Q(userprofile__mobile_number__isnull=False)
        ).distinct().only("id", "phone_number", "blocked_reason"):
            for p_digits, p_last10 in collect_user_phones(candidate):
                if p_digits == digits or (last10 and p_last10 == last10):
                    return candidate

    return None


def is_contact_blocked(email=None, phone_number=None):
    """
    Check if the given email or phone number belongs to a blocked contact or blocked/inactive user.
    Returns (is_blocked: bool, message: str | None).
    """
    from .models import BlockedContact

    norm_email = normalize_email(email)
    canon_email = canonicalize_email(norm_email) if norm_email else ""
    digits, last10 = normalize_phone(phone_number)

    q = Q()
    if norm_email:
        q |= Q(email=norm_email) | Q(canonical_email=canon_email)
    if digits:
        q |= Q(phone_number=digits)
        if last10:
            q |= Q(phone_last10=last10)

    if q:
        record = BlockedContact.objects.filter(is_active=True).filter(q).order_by("-created_at").first()
        if record:
            return True, format_blocked_message(record.reason)

    fallback_user = _find_blocked_user_fallback(norm_email, canon_email, digits, last10)
    if fallback_user:
        return True, format_blocked_message(getattr(fallback_user, "blocked_reason", ""))

    return False, None


def check_registration_block(email=None, phone_number=None):
    """
    Check email and phone_number independently so callers can attach field-specific errors.
    Returns a dict of {field_name: message} (empty dict if not blocked).
    """
    errors = {}
    if email:
        blocked, msg = is_contact_blocked(email=email)
        if blocked:
            errors["email"] = msg
    if phone_number:
        blocked, msg = is_contact_blocked(phone_number=phone_number)
        if blocked:
            errors["phone_number"] = msg
    return errors

