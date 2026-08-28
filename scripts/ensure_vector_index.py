#!/usr/bin/env python
"""Idempotently create an S3 Vectors bucket and index.

The Terraform AWS provider has no aws_s3vectors_* resources, so this is
driven from a local-exec provisioner. It replaces an inline shell heredoc
that silently no-opped under Windows cmd.exe while still reporting success
to Terraform -- leaving the index missing and the Route stage failing at
runtime with "The specified index could not be found".

Exits non-zero on real failure so Terraform surfaces the problem.

Usage:
    python scripts/ensure_vector_index.py \
        --bucket NAME --index NAME [--dimension 1024] \
        [--metric cosine] [--region ap-south-1]
"""

from __future__ import annotations

import argparse
import sys

import boto3
from botocore.exceptions import ClientError


def _exists(fn, **kwargs) -> bool:
    try:
        fn(**kwargs)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("NotFoundException", "ResourceNotFoundException"):
            return False
        raise


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--dimension", type=int, default=1024)
    ap.add_argument("--metric", default="cosine")
    ap.add_argument("--region", default="ap-south-1")
    a = ap.parse_args()

    c = boto3.client("s3vectors", region_name=a.region)

    if _exists(c.get_vector_bucket, vectorBucketName=a.bucket):
        print("vector bucket already exists: %s" % a.bucket)
    else:
        c.create_vector_bucket(vectorBucketName=a.bucket)
        print("created vector bucket: %s" % a.bucket)

    if _exists(c.get_index, vectorBucketName=a.bucket, indexName=a.index):
        existing = c.get_index(vectorBucketName=a.bucket, indexName=a.index)["index"]
        dim = existing.get("dimension")
        if dim not in (None, a.dimension):
            print(
                "ERROR: index %s exists with dimension %s, expected %s. "
                "Delete it or change embedding_dim -- vectors of the wrong "
                "width are rejected at write time."
                % (a.index, dim, a.dimension),
                file=sys.stderr,
            )
            return 1
        print("index already exists: %s (dimension=%s)" % (a.index, dim))
        return 0

    c.create_index(
        vectorBucketName=a.bucket,
        indexName=a.index,
        dimension=a.dimension,
        distanceMetric=a.metric,
        dataType="float32",
    )
    print("created index: %s (dimension=%d, metric=%s)" % (a.index, a.dimension, a.metric))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ClientError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        raise SystemExit(1)
