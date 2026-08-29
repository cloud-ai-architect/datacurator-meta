"""Lambda handler for the API Gateway /feedback endpoint."""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

import boto3

VALID_LABELS = {"misclassified", "misrouted", "good"}


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    """Handle a feedback submission.

    Event shape (API Gateway HTTP API v2):
        {
            "body": "{\"chunk_id\": \"...\", \"label\": \"misclassified\"}",
            "requestContext": {"http": {"method": "POST"}}
        }
    """
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _error(400, "INVALID_BODY", "Body must be valid JSON")

    chunk_id = body.get("chunk_id")
    label = body.get("label")
    suggested_class = body.get("suggested_class")
    notes = body.get("notes")

    if not chunk_id:
        return _error(400, "INVALID_BODY", "chunk_id is required")
    if label not in VALID_LABELS:
        return _error(400, "INVALID_LABEL", f"label must be one of {VALID_LABELS}")

    # User identification from request context (JWT or IAM sub)
    request_ctx = event.get("requestContext", {}).get("http", {})
    user_id = request_ctx.get("sourceIp", "anonymous")  # fallback

    feedback_id = str(uuid.uuid4())

    dynamodb = boto3.client("dynamodb", region_name="ap-south-1")
    try:
        dynamodb.put_item(
            TableName=os.environ.get("FEEDBACK_TABLE", "datacurator-feedback-dev"),
            Item={
                "feedback_id": {"S": feedback_id},
                "chunk_id": {"S": chunk_id},
                "user_id": {"S": user_id},
                "label": {"S": label},
                "suggested_class": {"S": suggested_class or ""},
                "notes": {"S": notes or ""},
                "resolved": {"BOOL": False},
                "created_at": {"S": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                "ttl": {"N": str(int(time.time()) + 365 * 24 * 60 * 60)},
            },
        )
    except Exception as exc:
        return _error(500, "INTERNAL_ERROR", str(exc))

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "feedback_id": feedback_id,
                "chunk_id": chunk_id,
                "status": "recorded",
                "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        ),
    }


def _error(status: int, code: str, message: str) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": code, "message": message}),
    }
