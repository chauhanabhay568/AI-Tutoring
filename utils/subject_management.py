"""Helpers for managing subjects inside student profiles."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def canonical_subject_name(name: Any) -> str:
    """Return the display form of a subject name with surrounding whitespace removed."""
    return str(name or "").strip()


def normalize_subject_name(name: Any) -> str:
    """Return a comparison key for case-insensitive subject matching."""
    return canonical_subject_name(name).casefold()


def get_subject_list(profile: dict[str, Any] | None) -> list[str]:
    """Return the profile's subject list as trimmed display names."""
    if not profile:
        return []

    raw_subjects = profile.get("subjects", [])
    if isinstance(raw_subjects, str):
        items = raw_subjects.split(",")
    elif isinstance(raw_subjects, (list, tuple, set)):
        items = list(raw_subjects)
    else:
        items = []

    subjects: list[str] = []
    for item in items:
        subject = canonical_subject_name(item)
        if subject:
            subjects.append(subject)
    return subjects


def get_subject_details(profile: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Return a deep copy of the profile's subject-details mapping."""
    if not profile:
        return {}

    subject_details = profile.get("subject_details", {})
    if not isinstance(subject_details, dict):
        return {}
    return deepcopy(subject_details)


def find_subject_key(subject_details: dict[str, dict[str, Any]], subject_name: Any) -> str | None:
    """Find the stored key for a subject name using trimmed case-insensitive matching."""
    target = normalize_subject_name(subject_name)
    if not target:
        return None

    for key in subject_details:
        if normalize_subject_name(key) == target:
            return key
    return None


def subject_exists(profile: dict[str, Any] | None, subject_name: Any) -> bool:
    """Return True when the profile already includes a subject with the same name."""
    target = normalize_subject_name(subject_name)
    if not target:
        return False

    if any(normalize_subject_name(subject) == target for subject in get_subject_list(profile)):
        return True

    return find_subject_key(get_subject_details(profile), subject_name) is not None


def build_add_subject_updates(
    profile: dict[str, Any] | None,
    subject_name: Any,
    subject_detail_values: dict[str, Any],
) -> dict[str, Any]:
    """Return updated profile fields for adding a new subject."""
    clean_name = canonical_subject_name(subject_name)
    if not clean_name:
        raise ValueError("Subject name is required.")
    if subject_exists(profile, clean_name):
        raise ValueError("A subject with this name already exists.")

    subjects = get_subject_list(profile)
    subject_details = get_subject_details(profile)
    subjects.append(clean_name)
    subject_details[clean_name] = deepcopy(subject_detail_values)
    return {
        "subjects": ", ".join(subjects),
        "subject_details": subject_details,
    }


def build_update_subject_updates(
    profile: dict[str, Any] | None,
    subject_name: Any,
    subject_detail_values: dict[str, Any],
) -> dict[str, Any]:
    """Return updated profile fields for editing an existing subject."""
    clean_name = canonical_subject_name(subject_name)
    if not clean_name:
        raise ValueError("Subject name is required.")

    subject_details = get_subject_details(profile)
    stored_key = find_subject_key(subject_details, clean_name)
    if stored_key is None:
        raise KeyError(f"Subject not found: {clean_name}")

    subject_details[stored_key] = deepcopy(subject_detail_values)
    return {
        "subjects": ", ".join(get_subject_list(profile)),
        "subject_details": subject_details,
    }


def build_delete_subject_updates(
    profile: dict[str, Any] | None,
    subject_name: Any,
) -> dict[str, Any]:
    """Return updated profile fields for deleting an existing subject."""
    clean_name = canonical_subject_name(subject_name)
    if not clean_name:
        raise ValueError("Subject name is required.")

    subject_list = get_subject_list(profile)
    subject_details = get_subject_details(profile)

    stored_key = find_subject_key(subject_details, clean_name)
    if stored_key is None:
        raise KeyError(f"Subject not found: {clean_name}")

    remaining_subjects = [subject for subject in subject_list if normalize_subject_name(subject) != normalize_subject_name(clean_name)]
    subject_details.pop(stored_key, None)

    return {
        "subjects": ", ".join(remaining_subjects),
        "subject_details": subject_details,
    }


def build_single_subject_profile(
    profile: dict[str, Any] | None,
    subject_name: Any,
) -> dict[str, Any]:
    """Return a copy of profile data scoped to a single selected subject."""
    subject_details = get_subject_details(profile)
    stored_key = find_subject_key(subject_details, subject_name)

    scoped_profile = dict(profile or {})
    if stored_key is None:
        scoped_profile["subject_details"] = {}
        scoped_profile["subjects"] = canonical_subject_name(subject_name)
        return scoped_profile

    scoped_profile["subject_details"] = {stored_key: deepcopy(subject_details[stored_key])}
    scoped_profile["subjects"] = stored_key
    return scoped_profile
