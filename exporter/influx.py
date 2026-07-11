"""Minimal InfluxDB 2.x line-protocol writer with basic retry handling."""

import time

import requests


def write_lines(lines, url, org, bucket, token, retries=3, backoff_seconds=2, timeout=10):
    """POST line-protocol lines to InfluxDB, retrying transient failures.

    Raises the last error if every attempt fails; callers decide whether that should crash
    the process or just be logged and skipped.
    """
    if not lines:
        return

    payload = "\n".join(lines)
    endpoint = f"{url.rstrip('/')}/api/v2/write"
    params = {"org": org, "bucket": bucket, "precision": "ns"}
    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "text/plain; charset=utf-8",
    }

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(endpoint, params=params, headers=headers, data=payload, timeout=timeout)
            if response.status_code // 100 == 2:
                return
            last_error = RuntimeError(f"InfluxDB returned {response.status_code}: {response.text[:200]}")
        except requests.RequestException as exc:
            last_error = exc

        if attempt < retries:
            time.sleep(backoff_seconds * attempt)

    raise last_error
