"""Test environment isolation.

Two of the pipeline stages build a boto3 client in ``setup()``. boto3 reads
its region and credentials from the ambient environment, which means those
tests passed on any developer machine that happened to have AWS configured
and failed in CI, where nothing is configured -- a failure that says nothing
about the code under test.

Pinning fake values here makes the suite hermetic in both directions. The
tests no longer depend on the machine they run on, and a stage that reaches
past its mock cannot reach real AWS with a real developer's credentials: it
gets an invalid-token error instead of touching a live account.

``autouse`` with session scope so it applies before any client is built, and
``setdefault`` so a deliberately exported value still wins.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

_FAKE_ENV = {
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_REGION": "us-east-1",
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_SECURITY_TOKEN": "testing",
    "AWS_SESSION_TOKEN": "testing",
    "AWS_EC2_METADATA_DISABLED": "true",
}

# Cleared rather than set. botocore resolves an empty AWS_PROFILE as a
# profile literally named "", and raises ProfileNotFound before it ever
# reaches the region -- so unsetting it is the only way to stop a developer's
# named profile leaking into the suite.
_CLEARED = ("AWS_PROFILE",)


@pytest.fixture(scope="session", autouse=True)
def aws_test_environment() -> Iterator[None]:
    previous = {k: os.environ.get(k) for k in (*_FAKE_ENV, *_CLEARED)}
    for key in _CLEARED:
        os.environ.pop(key, None)
    for key, value in _FAKE_ENV.items():
        os.environ.setdefault(key, value)
    yield
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
