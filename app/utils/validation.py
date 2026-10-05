"""Small, dependency-free validator driven by each model's FIELDS spec."""
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
URL_RE = re.compile(r"^(https?://|/|mailto:|tel:)\S+$", re.IGNORECASE)
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
DATE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
COLOR_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
TAG_RE = re.compile(r"<[^>]*>")


class ValidationError(Exception):
    def __init__(self, errors):
        super().__init__("Validation failed")
        self.errors = errors


def slugify(text):
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:200] or "item"


def strip_tags(value):
    """Plain-text fields must not contain HTML (basic XSS protection)."""
    return TAG_RE.sub("", value)


def _clean(name, spec, value, errors):
    t = spec["type"]
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None

    if t in ("string", "slug"):
        value = strip_tags(str(value).strip())
        if "max" in spec and len(value) > spec["max"]:
            errors[name] = f"Must be at most {spec['max']} characters"
        return value
    if t == "text":
        # Long text / markdown – kept as-is, the frontend renders it safely.
        return str(value)
    if t == "integer":
        try:
            value = int(value)
        except (TypeError, ValueError):
            errors[name] = "Must be a whole number"
            return None
        if "min" in spec and value < spec["min"]:
            errors[name] = f"Must be at least {spec['min']}"
        if "max" in spec and value > spec["max"]:
            errors[name] = f"Must be at most {spec['max']}"
        return value
    if t == "boolean":
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("1", "true", "yes", "on")
    if t in ("url", "image"):
        value = str(value).strip()
        if not URL_RE.match(value):
            errors[name] = "Must be a valid URL (http://, https:// or /uploads/...)"
        return value
    if t == "email":
        value = str(value).strip().lower()
        if not EMAIL_RE.match(value):
            errors[name] = "Must be a valid email address"
        return value
    if t == "choice":
        if value not in spec["choices"]:
            errors[name] = f"Must be one of: {', '.join(spec['choices'])}"
        return value
    if t == "month":
        value = str(value).strip()[:7]
        if not MONTH_RE.match(value):
            errors[name] = "Must be in YYYY-MM format"
        return value
    if t == "date":
        value = str(value).strip()[:10]
        if not DATE_RE.match(value):
            errors[name] = "Must be in YYYY-MM-DD format"
        return value
    if t == "color":
        value = str(value).strip()
        if not COLOR_RE.match(value):
            errors[name] = "Must be a hex colour like #ff3366"
        return value
    if t == "list":
        if isinstance(value, (list, tuple)):
            items = [strip_tags(str(v).strip()) for v in value if str(v).strip()]
        else:
            items = [strip_tags(v.strip()) for v in str(value).split(",") if v.strip()]
        return ",".join(items)
    return value


def validate(fields, payload, partial=False):
    """
    Returns a cleaned dict of values ready to set on the model.
    partial=True (PUT on existing row) only checks fields present in payload.
    """
    if not isinstance(payload, dict):
        raise ValidationError({"_": "Request body must be a JSON object"})

    errors, cleaned = {}, {}
    for name, spec in fields.items():
        present = name in payload
        if not present:
            if not partial and spec.get("required"):
                errors[name] = "This field is required"
            elif not partial and "default" in spec:
                cleaned[name] = spec["default"]
            continue
        value = _clean(name, spec, payload[name], errors)
        if value is None and spec.get("required"):
            errors[name] = "This field is required"
        cleaned[name] = value

    if errors:
        raise ValidationError(errors)
    return cleaned
