"""Generate the frontend-team API playbook PDF from the merged OpenAPI schema.

Reads ``docs/openapi.json`` (refresh it first with ``scripts/export_openapi.py``),
renders a fully-structured HTML document — every service, endpoint, parameter,
request-body field, response field, and a complete component-schema appendix —
then prints it to PDF with headless Edge.

Run from ``bank_system``:

    python scripts/export_openapi.py
    python scripts/export_playbook_pdf.py
"""

from __future__ import annotations

import html
import json
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "openapi.json"
HTML_PATH = ROOT / "docs" / "api-playbook.html"
PDF_PATH = ROOT / "docs" / "neo-bank-api-playbook.pdf"

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

SERVICE_ORDER = [
    ("root", "Platform (root app)", ("/health", "/ready", "/bilan")),
    ("governance", "Orchestrator Governance", ("/governance",)),
    ("p1", "Pillar 1 &mdash; Candidates + Demo Flow", ("/p1",)),
    ("p2", "Pillar 2 &mdash; Credit Scoring &amp; Risk Rating", ("/p2",)),
    ("p3", "Pillar 3 &mdash; Loan Lifecycle &amp; Execution", ("/p3",)),
    ("p4", "Pillar 4 &mdash; Prudential Layer", ("/p4",)),
]

METHOD_ORDER = ["get", "post", "put", "patch", "delete"]


def esc(x) -> str:
    return html.escape(str(x), quote=True)


def md_simple(text: str) -> str:
    out = esc(text)
    while "**" in out:
        a, _, rest = out.partition("**")
        b, _, out = rest.partition("**")
        out = f"{a}<strong>{b}</strong>{out}"
    while "``" in out:
        a, _, rest = out.partition("``")
        b, _, out = rest.partition("``")
        out = f"{a}<code>{b}</code>{out}"
    out = out.replace("`", "&grave;")
    return out


def resolve_ref(node: dict, components: dict, _seen: tuple = ()) -> tuple[dict, str | None]:
    if not isinstance(node, dict):
        return node, None
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
        name = ref.rsplit("/", 1)[-1]
        if name in _seen:
            return {}, name
        target = components.get(name, {})
        resolved, inner_name = resolve_ref(target, components, _seen + (name,))
        return resolved, name
    return node, None


def deref(node: dict, components: dict) -> dict:
    schema, _ = resolve_ref(node, components)
    if "allOf" in schema:
        merged: dict = {"properties": {}, "required": []}
        for part in schema["allOf"]:
            p = deref(resolve_ref(part, components)[0], components)
            merged["properties"].update(p.get("properties", {}))
            merged["required"].extend(p.get("required", []))
        for k, v in schema.items():
            if k not in ("allOf", "properties", "required"):
                merged[k] = v
        return merged
    return schema


def type_str(node: dict, components: dict, depth: int = 0) -> str:
    schema, ref_name = resolve_ref(node, components)
    if ref_name and "properties" not in schema and "items" not in schema:
        return f"<a href=\"#schema-{esc(ref_name)}\"><code>{esc(ref_name)}</code></a>"
    if "anyOf" in schema or "oneOf" in schema:
        variants = schema.get("anyOf") or schema.get("oneOf")
        parts = [type_str(v, components, depth) for v in variants]
        nullish = any(p == "null" for p in parts)
        parts = [p for p in parts if p != "null"]
        joined = " | ".join(dict.fromkeys(parts))
        return f"{joined} | null" if nullish else joined
    t = schema.get("type")
    if t == "array" or "items" in schema:
        item = type_str(schema.get("items", {}), components, depth + 1)
        return f"array of {item}"
    if t == "string" and schema.get("format"):
        return f"string <span class=\"fmt\">({esc(schema['format'])})</span>"
    if t is None and "properties" in schema:
        return "object"
    if "enum" in schema:
        vals = ", ".join(f"<code>{esc(v)}</code>" for v in schema["enum"])
        return f"{esc(t or 'string')} — one of: {vals}"
    return esc(t or "object")


def field_table(node: dict, components: dict, caption: str = "") -> str:
    schema = deref(node, components)
    props = schema.get("properties") or {}
    if not props:
        if schema.get("type") == "array":
            return f"<p class=\"schema-note\">{type_str(schema, components)}"
        t = type_str(schema, components)
        if t:
            return f"<p class=\"schema-note\">{t}</p>"
        return ""
    required = set(schema.get("required") or [])
    rows = []
    for name, prop in props.items():
        p = deref(prop, components)
        _, ref_name = resolve_ref(prop, components)
        req = "yes" if name in required else ""
        default = ""
        if "default" in p:
            default = f"<code>{esc(json.dumps(p['default']))}</code>"
        desc = md_simple(p.get("description") or "")
        if "enum" in p and "one of" not in type_str(prop, components):
            vals = ", ".join(f"<code>{esc(v)}</code>" for v in p["enum"])
            desc = (desc + " " if desc else "") + f"one of: {vals}"
        if p.get("type") == "object" and p.get("properties") and not ref_name:
            sub = ", ".join(p["properties"].keys())
            desc = (desc + " " if desc else "") + f"fields: <code>{esc(sub)}</code>"
        if p.get("type") == "array" and not ref_name:
            items = p.get("items", {})
            if items.get("type") == "object" and items.get("properties"):
                sub = ", ".join(items["properties"].keys())
                desc = (desc + " " if desc else "") + f"item fields: <code>{esc(sub)}</code>"
        rows.append(
            f"<tr><td class=\"field\"><code>{esc(name)}</code></td>"
            f"<td class=\"type\">{type_str(prop, components)}</td>"
            f"<td class=\"req\">{req}</td>"
            f"<td class=\"def\">{default}</td>"
            f"<td>{desc}</td></tr>"
        )
    cap = f"<caption>{esc(caption)}</caption>" if caption else ""
    return (
        f"<table class=\"fields\">{cap}"
        "<thead><tr><th>Field</th><th>Type</th><th>Required</th><th>Default</th><th>Description</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def params_table(params: list, components: dict) -> str:
    if not params:
        return ""
    rows = []
    for p in params:
        p = deref(p, components)
        req = "yes" if p.get("required") else ""
        default = f"<code>{esc(json.dumps(p['default']))}</code>" if "default" in p else ""
        desc = md_simple(p.get("description") or "")
        rows.append(
            f"<tr><td class=\"field\"><code>{esc(p.get('name'))}</code></td>"
            f"<td>{esc(p.get('in'))}</td>"
            f"<td class=\"type\">{type_str(p.get('schema', {}), components)}</td>"
            f"<td class=\"req\">{req}</td><td class=\"def\">{default}</td><td>{desc}</td></tr>"
        )
    return (
        "<table class=\"fields\"><caption>Parameters</caption>"
        "<thead><tr><th>Name</th><th>In</th><th>Type</th><th>Required</th><th>Default</th><th>Description</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def responses_html(responses: dict, components: dict) -> str:
    blocks = []
    for status in sorted(responses.keys(), key=lambda s: (s != "200" and s != "201", s)):
        r = deref(responses[status], components)
        desc = md_simple(r.get("description") or "")
        content = r.get("content") or {}
        schema_html = ""
        for _ctype, media in content.items():
            if "schema" in media:
                schema = media["schema"]
                schema_html = field_table(schema, components)
                if not schema_html:
                    schema_html = f"<p class=\"schema-note\">{type_str(schema, components)}</p>"
                break
            if "example" in media:
                schema_html = f"<pre class=\"example\">{esc(json.dumps(media['example'], indent=2))}</pre>"
        cls = "ok" if str(status).startswith("2") else "err"
        blocks.append(
            f"<div class=\"resp {cls}\"><div class=\"resp-head\"><span class=\"status\">{esc(status)}</span> {desc}</div>"
            f"{schema_html}</div>"
        )
    return f"<div class=\"responses\"><div class=\"section-label\">Responses</div>{''.join(blocks)}</div>"


def request_body_html(operation: dict, components: dict) -> str:
    body = operation.get("requestBody") or {}
    if not body:
        return ""
    body = deref(body, components)
    content = body.get("content") or {}
    blocks = []
    for ctype, media in content.items():
        label = f"<span class=\"ctype\">{esc(ctype)}</span>"
        required = " <span class=\"req-pill\">required</span>" if body.get("required") else ""
        inner = ""
        if "schema" in media:
            inner = field_table(media["schema"], components)
            if not inner:
                inner = f"<p class=\"schema-note\">{type_str(media['schema'], components)}</p>"
        elif "example" in media:
            inner = f"<pre class=\"example\">{esc(json.dumps(media['example'], indent=2))}</pre>"
        blocks.append(f"<div class=\"body-block\">{label}{required}{inner}</div>")
    return f"<div class=\"request\"><div class=\"section-label\">Request body</div>{''.join(blocks)}</div>"


def render_operation(path: str, method: str, op: dict, path_params: list, components: dict) -> str:
    all_params = [p for p in (path_params + op.get("parameters", []))]
    summary = md_simple(op.get("summary") or "")
    description = md_simple(op.get("description") or "")
    op_id = esc(op.get("operationId") or "")
    tags = ", ".join(op.get("tags") or [])
    params = params_table(all_params, components)
    return (
        f"<div class=\"op\" id=\"op-{esc(op_id or (method + path))}\">"
        f"<div class=\"op-head\"><span class=\"method {esc(method)}\">{esc(method.upper())}</span>"
        f"<code class=\"path\">{esc(path)}</code></div>"
        f"<div class=\"op-meta\">{summary}"
        + (f"<div class=\"op-id\">operationId: <code>{op_id}</code>" + (f" · tags: {esc(tags)}" if tags else "") + "</div>" if op_id or tags else "")
        + "</div>"
        + (f"<p class=\"op-desc\">{description}</p>" if description else "")
        + params
        + request_body_html(op, components)
        + responses_html(op.get("responses") or {}, components)
        + "</div>"
    )


def service_of(path: str) -> str:
    if path.startswith("/governance"):
        return "governance"
    if path.startswith("/p1"):
        return "p1"
    if path.startswith("/p2"):
        return "p2"
    if path.startswith("/p3"):
        return "p3"
    if path.startswith("/p4"):
        return "p4"
    return "root"


CSS = """
@page { size: A4; margin: 14mm 12mm 16mm 12mm; }
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 9.5pt; color: #1a2332; line-height: 1.45; margin: 0; }
h1 { font-size: 22pt; margin: 0 0 4mm; color: #0b2545; }
h2 { font-size: 15pt; margin: 0 0 3mm; color: #0b2545; border-bottom: 2.5pt solid #0b2545; padding-bottom: 1.5mm; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 6mm 0 2mm; color: #13315c; page-break-after: avoid; }
p { margin: 1.5mm 0; }
code { font-family: Consolas, 'Courier New', monospace; font-size: 8.8pt; background: #eef2f7; padding: 0 1mm; border-radius: 2px; }
strong { color: #0b2545; }
.cover { page-break-after: always; }
.cover .sub { font-size: 11pt; color: #445; margin-bottom: 8mm; }
.meta { color: #667; font-size: 9pt; margin-bottom: 6mm; }
.svc-map { width: 100%; border-collapse: collapse; margin: 4mm 0; }
.svc-map th, .svc-map td { border: 0.5pt solid #c5d0de; padding: 1.6mm 2mm; text-align: left; vertical-align: top; }
.svc-map th { background: #e8eef6; }
.conventions { background: #f4f7fb; border-left: 3pt solid #2b6cb0; padding: 3mm 4mm; margin: 4mm 0; }
.conventions li { margin: 1mm 0; }
.service { page-break-before: always; }
.tag-desc { color: #556; font-style: italic; margin: 1mm 0 3mm; }
.op { border: 0.6pt solid #c9d4e2; border-radius: 3pt; margin: 3.5mm 0; padding: 2.5mm 3mm; page-break-inside: avoid; }
.op-head { display: flex; align-items: center; gap: 2.5mm; margin-bottom: 1.2mm; }
.method { font-family: Consolas, monospace; font-weight: 700; font-size: 8.5pt; color: #fff; padding: 0.6mm 2mm; border-radius: 2pt; letter-spacing: 0.4pt; }
.method.get { background: #2f855a; }
.method.post { background: #2b6cb0; }
.method.put { background: #b7791f; }
.method.patch { background: #975a16; }
.method.delete { background: #c53030; }
.path { font-size: 10pt; font-weight: 600; background: none; padding: 0; }
.op-meta { font-weight: 600; color: #13315c; }
.op-id { font-weight: 400; font-size: 8pt; color: #667; margin-top: 0.6mm; }
.op-desc { color: #334; margin: 1.5mm 0; }
.section-label { font-size: 8pt; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6pt; color: #4a5a72; margin: 2.5mm 0 1mm; }
table.fields { width: 100%; border-collapse: collapse; margin: 1mm 0 2mm; }
table.fields caption { text-align: left; font-size: 8pt; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6pt; color: #4a5a72; padding: 1mm 0; }
table.fields th, table.fields td { border: 0.5pt solid #c9d4e2; padding: 1.2mm 1.6mm; text-align: left; vertical-align: top; font-size: 8.6pt; }
table.fields th { background: #eef2f7; font-size: 8.2pt; }
td.field code { background: none; padding: 0; font-weight: 600; color: #13315c; }
td.type { font-size: 8.2pt; color: #334; }
td.req { text-align: center; color: #c53030; font-weight: 600; }
td.def { font-size: 8pt; }
.fmt { color: #667; font-size: 8pt; }
.resp { border-left: 2.5pt solid #c9d4e2; padding: 1mm 0 1mm 2.5mm; margin: 1.5mm 0; }
.resp.ok { border-color: #2f855a; }
.resp.err { border-color: #c53030; }
.resp-head .status { font-family: Consolas, monospace; font-weight: 700; }
.resp.ok .status { color: #2f855a; }
.resp.err .status { color: #c53030; }
.schema-note { font-size: 8.6pt; color: #445; margin: 0.5mm 0; }
.req-pill { background: #c53030; color: #fff; font-size: 7.5pt; padding: 0.3mm 1.5mm; border-radius: 2pt; }
.ctype { font-family: Consolas, monospace; font-size: 8.4pt; color: #2b6cb0; font-weight: 600; }
pre.example { background: #f4f7fb; border: 0.5pt solid #c9d4e2; padding: 2mm; font-size: 8pt; overflow-x: auto; }
.schema-app { page-break-before: always; }
.schema-block { page-break-inside: avoid; margin: 3mm 0; }
.schema-block h4 { font-family: Consolas, monospace; font-size: 10pt; margin: 0 0 1mm; color: #0b2545; border-bottom: 0.8pt dashed #c9d4e2; padding-bottom: 0.8mm; }
.toc a { color: #2b6cb0; text-decoration: none; }
.toc li { margin: 0.8mm 0; }
.footer-note { color: #667; font-size: 8pt; margin-top: 8mm; }
a { color: #2b6cb0; text-decoration: none; }
"""


def build_html(schema: dict) -> str:
    info = schema.get("info", {})
    components = schema.get("components", {}).get("schemas", {})
    paths: dict = schema.get("paths", {})

    by_service: dict[str, dict] = {key: {} for key, _, _ in SERVICE_ORDER}
    for path, item in paths.items():
        svc = service_of(path)
        by_service[svc][path] = item

    toc_items = []
    sections = []

    for svc_key, svc_title, _prefixes in SERVICE_ORDER:
        svc_paths = by_service[svc_key]
        if not svc_paths:
            continue
        ops_html = []
        tag_groups: dict[str, list] = {}
        for path in svc_paths:
            item = svc_paths[path]
            path_params = item.get("parameters") or []
            for method in METHOD_ORDER:
                if method not in item:
                    continue
                op = item[method]
                tag = (op.get("tags") or ["general"])[0]
                tag_groups.setdefault(tag, []).append(
                    render_operation(path, method, op, path_params, components)
                )
        tag_meta = {t["name"]: t.get("description", "") for t in schema.get("tags", [])}
        for tag in tag_groups:
            tag_desc = md_simple(tag_meta.get(tag, ""))
            ops_html.append(
                f"<h3>{esc(tag)}</h3>"
                + (f"<p class=\"tag-desc\">{tag_desc}</p>" if tag_desc else "")
                + "".join(tag_groups[tag])
            )
        anchor = f"svc-{svc_key}"
        safe_title = svc_title.replace("&mdash;", "&#8212;").replace("&amp;", "&")
        toc_items.append(f"<li><a href=\"#{anchor}\">{safe_title}</a> &mdash; {len(svc_paths)} paths</li>")
        sections.append(
            f"<section class=\"service\" id=\"{anchor}\"><h2>{safe_title}</h2>{''.join(ops_html)}</section>"
        )

    app_rows = []
    empty_note = '<p class="schema-note">no documented fields</p>'
    for name in sorted(components.keys()):
        block = field_table({"$ref": f"#/components/schemas/{name}"}, components) or empty_note
        anchor_html = f'<div class="schema-block" id="schema-{esc(name)}">'
        app_rows.append(f'{anchor_html}<h4>{esc(name)}</h4>{block}</div>')
        toc_items.append(
            f'<li class="toc-schema"><a href="#schema-{esc(name)}">'
            f'<code>{esc(name)}</code></a></li>'
        )

    manual = """
<section class="service" id="svc-manual"><h2>Appendix B &mdash; Endpoints not in the schema</h2>
<p>These routes exist but are excluded from the OpenAPI document (<code>include_in_schema=False</code>). Frontend still uses them.</p>
<table class="fields">
<thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>
<tbody>
<tr><td>GET</td><td><code>/</code></td><td>Demo SPA (serves <code>demo/dist</code> when built, otherwise the legacy static page).</td></tr>
<tr><td>GET</td><td><code>/health</code> (root, /p1, /p3, /p4)</td><td>Liveness probe — <code>{"status": "ok"}</code>. The root app also exposes <code>GET /ready</code> (restart-ok check, 503 on failure) and governance exposes <code>GET /governance/health</code>.</td></tr>
<tr><td>GET</td><td><code>/p1/demo/events/sse</code></td><td>Server-Sent Events stream for the demo board. Events arrive as <code>data: {json}</code> frames:
<ul>
<li><code>state_update</code> — full board snapshot after create/import/approve/disburse/seed</li>
<li><code>tick</code> — <code>{"tick": {...}, "state": {...}}</code> after each simulation month</li>
<li><code>reset</code> — full board snapshot after factory reset</li>
<li>keep-alive: empty <code>{}</code> frame every 30s</li>
</ul>
The board also polls <code>GET /p1/demo/state</code>; SSE is reserved for state <em>changes</em>.</td></tr>
<tr><td>GET</td><td><code>/assets/*</code></td><td>Vite build assets when <code>demo/dist</code> exists.</td></tr>
</tbody></table>
</section>
"""

    main_toc = "".join(
        f'<li><a href="#{a}">{t}</a></li>'
        for a, t in [
            ("svc-root", "Platform (root app)"),
            ("svc-governance", "Orchestrator Governance"),
            ("svc-p1", "Pillar 1"),
            ("svc-p2", "Pillar 2"),
            ("svc-p3", "Pillar 3"),
            ("svc-p4", "Pillar 4"),
        ]
    )
    svc_map = """
<table class="svc-map">
<tr><th>Prefix</th><th>Service</th><th>Owns</th></tr>
<tr><td><code>/governance</code></td><td>Orchestrator governance</td><td>Canon versions, Master Lexicon, tier table, interface rules, CIS-1 CASS contract stub, SI-1 staging, amendments, veto log, PENDING register</td></tr>
<tr><td><code>/p1</code></td><td>Pillar 1 — intake + demo flow</td><td>Candidates, scoring/approval/disbursement demo loop, board state, simulation tick, SSE</td></tr>
<tr><td><code>/p2</code></td><td>Pillar 2 — credit scoring</td><td>BRR/PD/LGD/EAD/EL, versioned BRR&rarr;PD grid, early-warning signals, override records, CASS feed contract</td></tr>
<tr><td><code>/p3</code></td><td>Pillar 3 — loan execution</td><td>Facilities, P2 packets, audit trail, postings, core-banking ledger, reconciliation, lifecycle actions</td></tr>
<tr><td><code>/p4</code></td><td>Pillar 4 — prudential layer</td><td>Buffer sub-accounts, guarantee-pool adequacy, capital snapshot, IFRS 9 staging, two-track veto, mode gate, pledge intake/release</td></tr>
<tr><td><code>/bilan</code> + root</td><td>Platform</td><td>French-PCG balance sheet from the shared store, <code>/health</code>, <code>/ready</code></td></tr>
</table>
"""
    op_count = sum(
        1 for p in paths.values() for m in p if m in METHOD_ORDER
    )

    doc = []
    doc.append('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">')
    doc.append('\n<title>Neo-Bank API Playbook</title>\n<style>')
    doc.append(CSS)
    doc.append('</style>\n</head>\n<body>\n<section class="cover">')
    doc.append('\n<h1>Neo-Bank MSME &mdash; API Playbook</h1>')
    doc.append(
        f'\n<p class="sub">Complete REST surface of the composed platform: '
        f'{esc(info.get("title", ""))} v{esc(info.get("version", ""))}</p>'
    )
    doc.append(
        f'\n<p class="meta">Generated {date.today().isoformat()} from the merged '
        f'OpenAPI schema &middot; {len(paths)} paths &middot; {op_count} operations '
        f'&middot; {len(components)} component schemas</p>'
    )
    doc.append("""
<div class="conventions">
<strong>How to read this playbook</strong>
<ul>
<li><strong>Base URL</strong> &mdash; every path is relative to <code>http://localhost:8000</code>. All five services are mounted in one process.</li>
<li><strong>Wire format</strong> &mdash; flat JSON everywhere: enums arrive as plain strings (<code>"TRACK_1_CLASSICAL"</code>), datetimes as ISO-8601 strings. No internal persistence markers.</li>
<li><strong>Errors</strong> &mdash; uniform body <code>{"detail": "..."}</code>. Semantics: <strong>404</strong> unknown identifier, <strong>409</strong> prudential veto / state-machine conflict / governance PENDING, <strong>422</strong> validation gate (unconfirmed packet, amounts outside outstanding, out-of-scope product).</li>
<li><strong>Auth</strong> &mdash; none (demo deployment; CORS is open).</li>
<li><strong>Reading order for a demo</strong> &mdash; create a candidate in <strong>Pillar 1</strong> &rarr; submit (Pillar 2 scores it) &rarr; approve &rarr; disburse; then watch <strong>Pillar 3</strong> facilities/postings/ledger and <strong>Pillar 4</strong> buffer balances / capital snapshot / veto state update.</li>
<li><strong>Veto semantics</strong> &mdash; <code>GET /p4/veto/consult</code> is the state <em>Pillar 2</em> must consult before confirming a packet. Pillar 3 never sees a veto event; it only ever sees a confirmed packet or none.</li>
<li><strong>Per-service docs</strong> &mdash; each sub-app also serves its own Swagger at <code>/p1/docs</code>, <code>/p2/docs</code>, <code>/p3/docs</code>, <code>/p4/docs</code>, <code>/governance/docs</code>.</li>
</ul>
</div>
""")
    doc.append(svc_map)
    doc.append('\n<h3>Contents</h3>\n<ol class="toc">')
    doc.append(main_toc)
    doc.append(
        f'\n<li>Appendix A &mdash; Component schema catalogue '
        f'({len(components)} schemas)</li>'
    )
    doc.append('\n<li>Appendix B &mdash; Endpoints not in the schema (SSE, health probes)</li>')
    doc.append('\n</ol>\n</section>\n')
    doc.append("".join(sections))
    doc.append("""
<section class="schema-app" id="svc-appendix-a"><h2>Appendix A &mdash; Component schema catalogue</h2>
<p>Every named request/response schema referenced by the endpoints above.</p>
""")
    doc.append("".join(app_rows))
    doc.append('</section>\n')
    doc.append(manual)
    doc.append(
        '\n<p class="footer-note">Generated by scripts/export_playbook_pdf.py '
        'from docs/openapi.json &mdash; regenerate after API changes.</p>'
    )
    doc.append('\n</body>\n</html>\n')
    return "".join(doc)


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    HTML_PATH.write_text(build_html(schema), encoding="utf-8")
    print(f"Wrote {HTML_PATH}")
    subprocess.run(
        [
            EDGE,
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={PDF_PATH}",
            HTML_PATH.resolve().as_uri(),
        ],
        check=True,
        capture_output=True,
        timeout=120,
    )
    print(f"Wrote {PDF_PATH} ({PDF_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
