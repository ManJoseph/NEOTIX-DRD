from datetime import datetime, time, timedelta

from django.db import connection
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import DatasetRequest, Episode, EpisodeQuality, RequestStatus


def build_analytics(start_date, end_date):
    local_timezone = timezone.get_default_timezone()
    start = timezone.make_aware(datetime.combine(start_date, time.min), local_timezone)
    # Include the entire end date by stopping at midnight on the following day.
    stop = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min), local_timezone)

    episodes = Episode.objects.filter(recorded_at__gte=start, recorded_at__lt=stop)
    daily_counts = (
        episodes.annotate(day=TruncDate("recorded_at", tzinfo=local_timezone))
        .values("day", "robot_id")
        .annotate(count=Count("id"))
        .order_by("day", "robot_id")
    )
    top_tasks = (
        episodes.filter(quality=EpisodeQuality.GOOD)
        .values("task_name")
        .annotate(count=Count("id"))
        .order_by("-count", "task_name")[:5]
    )

    # Requests are selected by submission date, not deadline or delivery date.
    requests = DatasetRequest.objects.filter(created_at__gte=start, created_at__lt=stop)
    status_rows = requests.values("status").annotate(count=Count("id"))
    counts_by_status = {status: 0 for status in RequestStatus.values}
    for row in status_rows:
        counts_by_status[row["status"]] = row["count"]

    # PostgreSQL calculates the median; Python receives only the single result.
    # Values are passed separately as parameters, never inserted into SQL text.
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT percentile_cont(0.5) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (delivered_at - created_at))
            )
            FROM desk_datasetrequest
            WHERE created_at >= %s AND created_at < %s
              AND delivered_at IS NOT NULL
            """,
            [start, stop],
        )
        median_delivery_seconds = cursor.fetchone()[0]

    return {
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "Africa/Kigali",
        "episodes_per_day_per_robot": list(daily_counts),
        "request_fulfilment": {
            "counts_by_status": counts_by_status,
            "median_delivery_seconds": median_delivery_seconds,
        },
        "top_good_tasks": list(top_tasks),
    }
