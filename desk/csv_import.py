import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Episode


CSV_COLUMNS = [
    "episode_id", "robot_id", "task_name", "recorded_at",
    "duration_seconds", "operator_name", "quality",
]


def clean_episode_row(row):
    # Remove surrounding whitespace from every CSV value.
    data = {}
    for field in CSV_COLUMNS:
        value = row[field].strip()
        if not value:
            raise ValueError(f"Missing required value: {field}.")
        data[field] = value

    data["episode_id"] = data["episode_id"].upper()
    data["robot_id"] = data["robot_id"].lower()
    data["task_name"] = " ".join(data["task_name"].split()).lower()
    data["quality"] = data["quality"].lower()

    try:
        recorded_at = datetime.fromisoformat(data["recorded_at"])
    except ValueError:
        try:
            recorded_at = datetime.strptime(data["recorded_at"], "%d/%m/%Y %H:%M")
        except ValueError:
            raise ValueError("Invalid recorded_at date.")
    # Export times without an offset are interpreted as Kigali time.
    if timezone.is_naive(recorded_at):
        recorded_at = timezone.make_aware(recorded_at, timezone.get_default_timezone())
    if recorded_at > timezone.now():
        raise ValueError("recorded_at cannot be in the future.")
    data["recorded_at"] = recorded_at

    try:
        duration = Decimal(data["duration_seconds"])
    except InvalidOperation:
        raise ValueError("duration_seconds must be a number.")
    if not duration.is_finite() or duration <= 0 or duration > 3600:
        raise ValueError("duration_seconds must be greater than 0 and at most 3600.")
    data["duration_seconds"] = duration

    # Reuse model field validators for choices, lengths, and decimal precision.
    episode = Episode(**data)
    episode.clean_fields()
    return data


def import_episodes(text):
    # Parse the entire bounded upload first, so broken CSV syntax causes no writes.
    try:
        rows = []
        reader = csv.reader(StringIO(text.lstrip("\ufeff")), strict=True)
        for row in reader:
            if len(rows) >= 10001:
                raise ValueError("CSV files must contain at most 10000 data records.")
            rows.append(row)
    except csv.Error as error:
        raise ValueError(f"Malformed CSV: {error}")
    if not rows:
        raise ValueError("The CSV file is empty.")

    header = [column.strip().lower() for column in rows[0]]
    if len(header) != len(CSV_COLUMNS) or set(header) != set(CSV_COLUMNS):
        raise ValueError("CSV header must contain exactly: " + ", ".join(CSV_COLUMNS))

    report = {"imported": 0, "skipped": 0, "skipped_rows": []}
    # Unexpected database failures roll back this import; invalid rows are reported.
    with transaction.atomic():
        for row_number, values in enumerate(rows[1:], start=2):
            episode_id = ""
            try:
                if not values or all(not value.strip() for value in values):
                    raise ValueError("Blank row.")
                if len(values) != len(header):
                    raise ValueError(f"Expected {len(header)} columns; found {len(values)}.")
                row = dict(zip(header, values))
                episode_id = row["episode_id"].strip().upper()
                data = clean_episode_row(row)
            except (ValueError, ValidationError) as error:
                reason = "; ".join(error.messages) if isinstance(error, ValidationError) else str(error)
            else:
                episode, created = Episode.objects.get_or_create(
                    episode_id=data["episode_id"], defaults=data,
                )
                if created:
                    report["imported"] += 1
                    continue
                same_data = all(getattr(episode, field) == value for field, value in data.items())
                if same_data:
                    reason = "Duplicate episode_id; identical record already exists."
                else:
                    reason = "Conflicting episode_id; existing record kept unchanged."

            report["skipped"] += 1
            report["skipped_rows"].append({
                "row": row_number, "episode_id": episode_id, "reason": reason,
            })
    return report
