"""Merge mounted sub-app OpenAPI schemas into the root app's single playbook.

The orchestrator mounts five FastAPI sub-apps (governance, P1, P2, P3, P4);
FastAPI's default ``/openapi.json`` only describes the root app's own routes,
so each sub-app's ~100 operations were invisible from ``/docs``. This module
overrides the root app's ``openapi()`` to produce one merged schema:

* every sub-app path is re-prefixed with its mount point
  (``/facilities`` on the P3 app -> ``/p3/facilities`` in the playbook);
* ``operationId``s are prefixed with the service name so they stay unique
  across the composed document;
* component schemas are merged; on a name collision the later schema is
  renamed with its service prefix and its internal ``$ref``\\ s are rewritten;
* the curated tag list from :mod:`bank.core.openapi_tags` is applied.

Per-app docs URLs (``/p3/docs`` etc.) keep working untouched.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import FastAPI

from bank.core.openapi_tags import OPENAPI_TAGS

_REF_PREFIX = "#/components/schemas/"


def _rewrite_refs(node: Any, renames: dict[str, str]) -> None:
    """In-place rewrite of ``$ref`` targets according to ``renames``."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str) and value.startswith(_REF_PREFIX):
                name = value[len(_REF_PREFIX):]
                if name in renames:
                    node[key] = _REF_PREFIX + renames[name]
            else:
                _rewrite_refs(value, renames)
    elif isinstance(node, list):
        for item in node:
            _rewrite_refs(item, renames)


def merge_subapp_openapi(
    root_schema: dict,
    sub_apps: dict[str, tuple[str, FastAPI]],
    tags_metadata: list[dict] | None = None,
) -> dict:
    """Return one merged OpenAPI dict for the composed orchestrator app.

    ``sub_apps`` maps a short service key (``"p3"``) to
    ``(mount_prefix, sub_app)`` — the same instances that were mounted.
    """
    merged = deepcopy(root_schema)
    merged_paths: dict = merged.setdefault("paths", {})
    merged_schemas: dict = merged.setdefault("components", {}).setdefault("schemas", {})

    for service, (mount_prefix, sub_app) in sub_apps.items():
        sub = deepcopy(sub_app.openapi())

        # ---- component schemas (rename on collision, rewrite refs) --------
        renames: dict[str, str] = {}
        for name, schema in (sub.get("components", {}).get("schemas", {}) or {}).items():
            if name not in merged_schemas:
                continue
            if merged_schemas[name] == schema:
                continue  # identical definition — share the original name
            candidate = f"{service}_{name}"
            counter = 2
            while candidate in merged_schemas and merged_schemas[candidate] != schema:
                candidate = f"{service}_{name}_{counter}"
                counter += 1
            renames[name] = candidate
        if renames:
            _rewrite_refs(sub, renames)
        for name, schema in (sub.get("components", {}).get("schemas", {}) or {}).items():
            merged_schemas[renames.get(name, name)] = schema

        # ---- paths (re-prefix + unique operationIds) -----------------------
        for path, operations in (sub.get("paths", {}) or {}).items():
            full_path = mount_prefix + path
            target = merged_paths.setdefault(full_path, {})
            for method, operation in operations.items():
                if not isinstance(operation, dict):
                    target[method] = operation
                    continue
                operation = dict(operation)
                op_id = operation.get("operationId")
                operation["operationId"] = (
                    f"{service}_{op_id}"
                    if op_id
                    else f"{service}_{method}_{full_path.strip('/').replace('/', '_')}"
                )
                target[method] = operation

    # ---- one curated tag list for the whole playbook -----------------------
    if tags_metadata:
        merged["tags"] = deepcopy(tags_metadata)
    return merged


def install_merged_openapi(app: FastAPI, sub_apps: dict[str, tuple[str, FastAPI]]) -> None:
    """Override ``app.openapi`` so ``/openapi.json`` and ``/docs`` serve the
    merged playbook. Call after the sub-apps are mounted (same instances)."""
    original_openapi = app.openapi
    cache: dict[str, dict | None] = {"schema": None}

    def custom_openapi() -> dict:
        if cache["schema"] is None:
            root_schema = original_openapi()
            cache["schema"] = merge_subapp_openapi(root_schema, sub_apps, OPENAPI_TAGS)
            app.openapi_schema = cache["schema"]
        return cache["schema"]

    app.openapi = custom_openapi  # type: ignore[method-assign]
