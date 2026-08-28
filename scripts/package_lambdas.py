#!/usr/bin/env python
"""Build and deploy DataCurator Lambda packages.

Terraform provisions the functions with a placeholder stub and ignores code
changes (see modules/lambdas/main.tf). This script owns code delivery.

Strategy: fetch the currently deployed bundle -- which already carries the
Linux-built dependency set -- swap in the local `src/` tree, and push the
result back. This avoids rebuilding manylinux wheels on a dev machine, which
is the usual source of "works locally, ImportError in Lambda".

Usage:
    python scripts/package_lambdas.py --dry-run
    python scripts/package_lambdas.py
    python scripts/package_lambdas.py --function datacurator-dev-parse
"""

from __future__ import annotations

import argparse
import io
import pathlib
import sys
import tempfile
import urllib.request
import zipfile

import boto3

REGION = "ap-south-1"
PREFIX = "datacurator-dev-"
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def deployed_functions(client) -> list[str]:
    names: list[str] = []
    paginator = client.get_paginator("list_functions")
    for page in paginator.paginate():
        names += [
            f["FunctionName"]
            for f in page["Functions"]
            if f["FunctionName"].startswith(PREFIX)
        ]
    return sorted(names)


def fetch_bundle(client, function_name: str) -> bytes:
    url = client.get_function(FunctionName=function_name)["Code"]["Location"]
    with urllib.request.urlopen(url) as resp:
        return resp.read()


def local_src_files() -> list[tuple[str, bytes]]:
    """Every .py under src/, as (archive_name, content)."""
    src = REPO_ROOT / "src"
    out: list[tuple[str, bytes]] = []
    for path in sorted(src.rglob("*.py")):
        arc = path.relative_to(REPO_ROOT).as_posix()
        out.append((arc, path.read_bytes()))
    return out


def rebuild(bundle: bytes, src_files: list[tuple[str, bytes]]) -> tuple[bytes, int, int]:
    """Return (new_zip, replaced_count, added_count)."""
    src_map = dict(src_files)
    replaced = added = 0
    buf = io.BytesIO()

    with zipfile.ZipFile(io.BytesIO(bundle)) as old:
        existing = set(old.namelist())
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as new:
            for item in old.infolist():
                if item.filename in src_map:
                    new.writestr(item, src_map[item.filename])
                    replaced += 1
                else:
                    new.writestr(item, old.read(item.filename))
            for arc, content in src_files:
                if arc not in existing:
                    new.writestr(arc, content)
                    added += 1

    return buf.getvalue(), replaced, added


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="build but do not upload")
    ap.add_argument("--function", help="deploy a single function (default: all)")
    args = ap.parse_args()

    client = boto3.client("lambda", region_name=REGION)
    targets = [args.function] if args.function else deployed_functions(client)
    if not targets:
        print("no functions found with prefix %r" % PREFIX, file=sys.stderr)
        return 1

    src_files = local_src_files()
    print("local src/: %d python files" % len(src_files))

    print("fetching reference bundle from %s ..." % targets[0])
    bundle = fetch_bundle(client, targets[0])
    print("  reference bundle: %.1f MB" % (len(bundle) / 1e6))

    payload, replaced, added = rebuild(bundle, src_files)
    print("  replaced %d, added %d -> %.1f MB" % (replaced, added, len(payload) / 1e6))

    if added:
        print("  NEW FILES: %s" % ", ".join(
            a for a, _ in src_files
            if a not in set(zipfile.ZipFile(io.BytesIO(bundle)).namelist())))

    if args.dry_run:
        out = pathlib.Path(tempfile.gettempdir()) / "datacurator-lambda.zip"
        out.write_bytes(payload)
        print("dry-run: wrote %s" % out)
        return 0

    for name in targets:
        client.update_function_code(FunctionName=name, ZipFile=payload, Publish=False)
        print("  deployed -> %s" % name)

    print("done: %d function(s) updated" % len(targets))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
