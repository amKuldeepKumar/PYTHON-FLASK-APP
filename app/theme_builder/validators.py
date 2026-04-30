from __future__ import annotations

from .catalog import get_feature_groups


def validate_builder_payload(payload: dict) -> dict:
    errors: dict[str, str] = {}
    field_index = {}

    for group in get_feature_groups():
        for field in group.fields:
            field_index[field.key] = field

    for key, field in field_index.items():
        value = payload.get(key)

        if field.required and (value is None or str(value).strip() == ""):
            errors[key] = f"{field.label} is required."
            continue

        if field.field_type == "range" and value not in (None, ""):
            try:
                num = float(value)
                if num < 0 or num > 100:
                    errors[key] = f"{field.label} must be between 0 and 100."
            except Exception:
                errors[key] = f"{field.label} must be numeric."

        if field.field_type == "select" and field.options:
            valid = {opt.value for opt in field.options}
            if value not in (None, "") and value not in valid:
                errors[key] = f"{field.label} has an invalid option."

    return errors