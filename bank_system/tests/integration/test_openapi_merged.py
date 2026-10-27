"""The composed root OpenAPI schema is one complete API playbook.

Asserts that the merged schema at the root app includes every service's
paths under their mount prefixes, that operationIds are unique, that no
double-prefix remnant (``/api/v1/p3/p3``) survives, and that the typed
response schemas are present as named components.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bank.orchestrator.main import app


@pytest.fixture(scope="module")
def schema() -> dict:
    # Fresh schema each test session (cached on the app afterwards).
    app.openapi_schema = None
    return app.openapi()


def test_all_service_paths_present(schema: dict) -> None:
    paths = schema["paths"]
    # One representative path per mounted service + the root bilan.
    assert "/health" in paths
    assert "/bilan" in paths
    assert "/governance/api/v1/canon/current" in paths
    assert "/p1/candidates" in paths
    assert "/p2/v1/score" in paths
    assert "/p3/facilities" in paths
    assert "/p4/buffer/balances" in paths
    assert "/p4/veto/consult" in paths
    assert "/p4/mode" in paths


def test_no_double_prefix_remnants(schema: dict) -> None:
    for path in schema["paths"]:
        assert "/api/v1/p3/p3" not in path
        assert "/api/v1/p4/p4" not in path
        assert not path.startswith("/p3/api/v1")
        assert not path.startswith("/p4/api/v1")


def test_operation_ids_unique(schema: dict) -> None:
    seen: set[str] = set()
    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            if not isinstance(operation, dict):
                continue
            op_id = operation.get("operationId")
            assert op_id, f"{method.upper()} {path} has no operationId"
            assert op_id not in seen, f"duplicate operationId {op_id}"
            seen.add(op_id)


def test_typed_response_schemas_present(schema: dict) -> None:
    schemas = schema.get("components", {}).get("schemas", {})
    for name in (
        "FacilitySummary",
        "PostingEventOut",
        "CapitalSnapshotOut",
        "VetoConsultOut",
        "BufferBalancesOut",
        "PoolAdequacyOut",
        "ErrorOut",
    ):
        assert name in schemas, f"missing response schema {name}"


def test_descriptions_on_pillar_endpoints(schema: dict) -> None:
    facilities = schema["paths"]["/p3/facilities"]["get"]
    assert facilities.get("summary")
    assert facilities.get("description")
    consult = schema["paths"]["/p4/veto/consult"]["get"]
    assert "Pillar 2" in (consult.get("description") or "")


def test_root_docs_serve_merged_schema() -> None:
    client = TestClient(app)
    r = client.get("/openapi.json")
    assert r.status_code == 200
    data = r.json()
    assert "/p3/facilities" in data["paths"]
    assert "/p4/buffer/balances" in data["paths"]
