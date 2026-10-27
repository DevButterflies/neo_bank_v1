"use strict";

/* ============================================================
   Bank Orchestrator Demo SPA
   Data surface 100% live HTTP against the mounted sub-apps over
   the shared KvStore file. Routes (verified against OpenAPI):
     GET  /health, /ready
     POST /p2/v1/score, GET /p2/v1/brr-pd-grid, /p2/v1/category-weights/<seg>
     GET  /p3/api/v1/p3/facilities, /audit, /postings, /ledger, /reconcile, /packets
     POST /p3/api/v1/p3/{originate,disburse,prese,repayment,...}
     GET  /p4/api/v1/p4/{buffer/balances,capital/snapshot,pool/adequacy,ifrs9,mode,veto/consult,events}
     POST /p4/api/v1/p4/{staging-signal,required-guarantee-level,risk-packet,veto/track2,veto/lift-track1,mode/activate,mode/fallback,pledge/submit}
     GET  /governance/api/v1/{canon/current,canon/lineage,pillars,tiers,staging/*,pending,vetoes,lexicon/*,interfaces,cass-stub}
   ============================================================ */

/* ---------- tiny API helper ---------- */
async function api(path, { method = "GET", body } = {}) {
  const init = { method, headers: {} };
  if (body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  const res = await fetch(path, init);
  const raw = await res.text();
  let data = null;
  try { data = raw ? JSON.parse(raw) : null; } catch { data = raw; }
  return { ok: res.ok, status: res.status, data };
}

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));

function fmt(v) {
  if (v === null || v === undefined) return "–";
  if (typeof v === "number") {
    if (Number.isInteger(v)) return v.toLocaleString("en-US");
    return v.toLocaleString("en-US", { maximumFractionDigits: 4 });
  }
  return String(v);
}

/* ---------- pill colours ---------- */
const OK = /^(APPROVED|ACTIVE|REPAYING|RATIFIED|OK|CLEAR|TRUE|AUTO_APPROVE|CONVENTIONAL|OPERATIVE|ADEQUATE|READY|COMPLETE|WITHIN|CONFIRMED)$/;
const WARN = /^(CONDITIONAL|PENDING|DELINQUENT|SUPERSEDED|LOW|MEDIUM|HIGH_INTEREST|ADAPTIVE|PARTIAL)$/;
const BAD = /^(DEFAULT|RECOVERY|MANUAL_REVIEW|SHORTFALL|FROZEN|FALSE|ERROR|FAIL|BREACH|CRITICAL|EMERGING)$/;
const INFO = /^(CLOSED|RESTRUCTURING|GOVERNABLE|SANDBOX|INTERMEDIATE|MUTED)$/;

function pillTone(v) {
  const s = String(v).toUpperCase();
  if (OK.test(s)) return "ok";
  if (WARN.test(s)) return "warn";
  if (BAD.test(s)) return "bad";
  if (INFO.test(s)) return "info";
  return (typeof v === "string" && v.length <= 24) ? "mute" : "info";
}
const pill = (v, custom) =>
  `<span class="pill ${custom || pillTone(v)}">${esc(fmt(v))}</span>`;
const stagePill = (s) => {
  const n = Number(s);
  const t = n === 1 ? "ok" : n === 2 ? "warn" : n === 3 ? "bad" : "mute";
  return pill(s, t);
};

/* ---------- recursive value renderer (handles the __codec__ wire format) ---------- */
function isObjectLike(v) {
  return !!v && typeof v === "object" && !Array.isArray(v);
}

function renderKeyValue(obj) {
  if (!isObjectLike(obj)) return '<span class="muted">–</span>';
  let html = "";
  if ("__dc__" in obj)
    html += `<div class="kv"><span></span><span><b class="muted">${esc(obj.__dc__)}</b></span></div>`;
  for (const k of Object.keys(obj)) {
    if (k === "__dc__") continue;
    html += `<div class="kv"><span class="k">${esc(k)}</span><span class="v">${renderValue(obj[k], k)}</span></div>`;
  }
  return `<div class="kv">${html}</div>`;
}

function renderValue(v, key) {
  if (v === null || v === undefined) return '<span class="muted">–</span>';
  if (typeof v === "boolean") return pill(v ? "TRUE" : "FALSE");
  if (typeof v === "number") return `<span class="mono">${fmt(v)}</span>`;
  if (typeof v === "string") {
    if (key === "state" || key === "status" || key === "zone" ||
        key === "resulting_state" || key === "current_mode" || key === "mode")
      return pill(v);
    if (key === "stage" || /stage$/.test(key)) return stagePill(v);
    if (key === "brr") return pill("BRR " + v);
    return esc(v);
  }
  if (Array.isArray(v)) {
    if (v.length && v.every((x) => x && typeof x === "object" && !Array.isArray(x)))
      return renderTable(v);
    return `<div class="kv"><span class="k">array</span><span class="v mono">[${v.map((x) => renderValue(x)).join(", ")}]</span></div>`;
  }
  if (!isObjectLike(v)) return '<span class="muted">–</span>';
  if ("__enum__" in v) return pill(v.value);
  if ("__dt__" in v) return `<span class="mono">${esc(v.__dt__)}</span>`;
  if ("__tuple__" in v) return `<span class="mono">(${v.__tuple__.map((x) => renderValue(x)).join(", ")})</span>`;
  if ("__set__" in v) return `<span class="mono">set{${v.__set__.map((x) => renderValue(x)).join(", ")}}</span>`;
  // plain / nested dict -> collapsible
  const summary = Object.keys(v).filter((k) => k !== "__dc__").slice(0, 3)
    .map((k) => `${k}: ${String(v[k]).slice(0, 22)}`).join(" · ");
  return `<details class="kv-group"><summary>${esc(v.__dc__ || "{ " + summary + " }")}</summary>` +
         `<div class="inner">${renderKeyValue(v)}</div></details>`;
}

function unionKeys(rows) {
  const order = [];
  for (const r of rows) for (const k of Object.keys(r)) if (!order.includes(k)) order.push(k);
  return order.sort((a, b) => {
    const fa = rows.filter((r) => a in r).length;
    const fb = rows.filter((r) => b in r).length;
    return fb - fa;
  });
}

function renderTable(rows) {
  if (!rows || !rows.length) return `<div class="empty">No records.</div>`;
  const keys = unionKeys(rows);
  const head = keys.map((k) => `<th>${esc(k)}</th>`).join("");
  const body = rows
    .map((r) => `<tr>${keys.map((k) => `<td>${renderValue(r[k], k)}</td>`).join("")}</tr>`)
    .join("");
  return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function section(title, bodyNodes, tag) {
  const b = document.createElement("div");
  b.className = "panel-block";
  let extra = "";
  if (tag !== undefined) extra = ` <span class="tag">${esc(tag)}</span>`;
  b.innerHTML = `<h3>${esc(title)}${extra}</h3>`;
  for (const n of [].concat(bodyNodes)) b.appendChild(n);
  return b;
}
function el(tag, cls, html) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html !== undefined) n.innerHTML = html;
  return n;
}
function bodyHtml(html) {
  const n = document.createElement("div");
  n.innerHTML = html;
  return n;
}
function msgBar(kind, text) {
  const n = document.createElement("div");
  n.className = `msg-bar ${kind}`;
  n.textContent = text;
  return n;
}
function panelHead(title, desc, refresh) {
  const h = document.createElement("div");
  h.className = "panel-head";
  const left = el("div");
  left.innerHTML = `<h2>${esc(title)}</h2>${desc ? `<div class="desc">${esc(desc)}</div>` : ""}`;
  h.appendChild(left);
  const btn = document.createElement("button");
  btn.className = "btn";
  btn.textContent = "Refetch";
  btn.addEventListener("click", refresh || (() => {}));
  h.appendChild(btn);
  return h;
}
async function fetchMany(urls) {
  const out = {};
  await Promise.all(urls.map(async (u) => { out[u] = await api(u); }));
  return out;
}
function valueOr(d, fallback) {
  return d && d.ok && d.data !== null && d.data !== undefined ? d.data : fallback;
}

/* ============================================================
   VIEW: Dashboard
   ============================================================ */
const Dashboard = {
  async render() {
    const root = document.getElementById("panel-dashboard");
    root.replaceChildren(msgBar("info", "Loading dashboard…"));
    const E = {
      health: "/health",
      ready: "/ready",
      canon: "/governance/api/v1/canon/current",
      balances: "/p4/api/v1/p4/buffer/balances",
      capital: "/p4/api/v1/p4/capital/snapshot",
      adequacy: "/p4/api/v1/p4/pool/adequacy",
      ifrs9: "/p4/api/v1/p4/ifrs9",
      pillars: "/governance/api/v1/pillars",
      mode: "/governance/api/v1/staging/mode",
      stage: "/governance/api/v1/staging/stage",
      adaptive: "/governance/api/v1/staging/is-adaptive-active",
      pending: "/governance/api/v1/pending/summary",
      vetoConsult: "/p4/api/v1/p4/veto/consult",
    };
    const g = await fetchMany(Object.values(E));
    root.replaceChildren();

    const head = panelHead("Dashboard", "Live orchestration surface — every tile is a verified HTTP response from the mounted sub-apps.", () => this.render());
    root.appendChild(head);

    const ready = g[E.ready];
    if (ready.ok && ready.data && ready.data.checks && !ready.data.checks.p3_restart_ok) {
      root.appendChild(msgBar("bad", "P3 restart round-trip degraded: re-seed + restart required."));
    }

    // --- canon headline ---
    const canon = valueOr(g[E.canon], {});
    root.appendChild(section("Operative Canon (head of lineage)", [
      bodyHtml(`<div class="card-grid">${[
        ["Version", pill(canon.version_number, "info")],
        ["Name", esc(canon.name || "")],
        ["Status", pill(canon.status || "—")],
        ["Instrument", esc(canon.ratification_instrument || "—")],
        ["Ratified", `<span class="mono">${esc(canon.ratified_at || "—")}</span>`],
      ].map(([k, v]) => `<div class="card"><h4>${esc(k)}</h4><div>${v}</div></div>`).join("")}</div>` +
        `<div class="muted" style="margin-top:10px;font-size:12px">${esc(canon.change_summary || "")}</div>`),
    ], canon.version_number));

    // --- KPI cards ---
    const b = valueOr(g[E.balances], {});
    const cap = valueOr(g[E.capital], {});
    const aq = valueOr(g[E.adequacy], {});
    const mode = valueOr(g[E.mode], {});
    const adv = valueOr(g[E.adaptive], {});
    const tierOk = cap.tier_d_over_rwa >= (cap.tier_d_floor || 0.12);
    const aqStatus = aq.status || (aq.received >= aq.required ? "adequate" : "shortfall");

    const kpis = [
      ["EL Pool", fmt(b.el_pool), "reserve/provision pool", "card"],
      ["ULA Buffer", fmt(b.ula_buffer), "unallocated loss absorption", "card"],
      ["Liquidity Reserve", fmt(b.liquidity_reserve), "liquidity leg", "card"],
      ["RP Pool", fmt(b.rp_pool), "reverse-restoration pool", "card"],
      ["Tier D / RWA", `${(cap.tier_d_over_rwa * 100).toFixed(3)}%`, pill(tierOk ? "ADEQUATE" : "SHORTFALL"), "card"],
      ["RWA", fmt(cap.rwa), `floor ${(cap.tier_d_floor * 100).toFixed(0)}%`, "card"],
      ["Pledged received", fmt(aq.received), "required " + fmt(aq.required), "card"],
      ["Guarantee cover", pill(aqStatus, aqStatus === "adequate" ? "ok" : "bad"),
        aq.shortfall_amount ? "shortfall " + fmt(aq.shortfall_amount) : "", "card"],
    ];
    root.appendChild(section("Prudential KPIs", [
      bodyHtml(`<div class="card-grid">${kpis
        .map(([t, v, s]) => `<div class="card"><h4>${esc(t)}</h4><div class="big">${v}</div><div class="sub">${s}</div></div>`)
        .join("")}</div>`),
    ], mode.current_mode || (adv.adaptive ? "ADAPTIVE" : "CONVENTIONAL")));

    // --- IFRS9 by stage ---
    const ifrs = valueOr(g[E.ifrs9], {}) || {};
    const st = Object.fromEntries([[1, 0], [2, 0], [3, 0]]);
    Object.values(ifrs).forEach((r) => { st[r.stage] = (st[r.stage] || 0) + 1; });
    root.appendChild(section("IFRS9 staging (P2→P4)", [
      bodyHtml(`<div class="card-grid">${Object.entries(st)
        .map(([k, v]) => `<div class="card"><h4>Stage ${k}</h4><div class="big">${v}</div><div class="sub">facilities</div></div>`)
        .join("")}</div>`),
    ]));

    // --- governance detail ---
    const pillars = valueOr(g[E.pillars], []) || [];
    const pending = valueOr(g[E.pending], {}) || {};
    const vc = valueOr(g[E.vetoConsult], {}) || {};
    const stageMeta = valueOr(g[E.stage], {}) || {};
    root.appendChild(section("Staging state", [
      bodyHtml(`<div class="card-grid">${[
        ["Mode", pill(mode.current_mode || "—"), esc(mode.fallback_guarantee || mode.fallback || "")],
        ["Stage", `<span class="big">${esc(stageMeta.current_stage)}</span>`, "decision-gate stage"],
        ["Adaptive active", pill(adv.adaptive ? "TRUE" : "FALSE", adv.adaptive ? "ok" : "mute"), ""],
        ["Veto frozen", pill(vc.any_frozen ? "FROZEN" : "CLEAR", vc.any_frozen ? "bad" : "ok"),
          `track1 ${vc.track1_frozen ? "frozen" : "clear"} · track2 ${vc.track2_frozen_for_facility ? "frozen" : "clear"}`],
        ["Open follow-ups", `<span class="big">${fmt(pending.open)}</span>`, `${fmt(pending.total)} registered`],
      ].map(([t, v, s]) => `<div class="card"><h4>${esc(t)}</h4><div>${v}</div>${s ? `<div class="sub">${s}</div>` : ""}</div>`).join("")}</div>`),
    ], "governance"));

    // --- pillars ---
    if (pillars.length) {
      root.appendChild(section("Pillar boundary model (§5)", [
        bodyHtml(`<div class="card-grid">${pillars
          .map((p) =>
            `<div class="card"><h4>P${p.pillar_number} · ${esc(p.pillar_name)}</h4>` +
            `<div class="sub">${esc(p.canon_section_ref || "")}</div>` +
            (p.decides && p.decides.length ? `<div style="margin-top:6px"><b class="muted">decides</b><br>${esc(p.decides.join("; "))}</div>` : "") +
            (p.must_not_do && p.must_not_do.length ? `<div style="margin-top:6px;color:var(--bad)"><b>must not</b><br>${esc(p.must_not_do.join("; "))}</div>` : "") +
            `</div>`)
          .join("")}</div>`),
      ]);
    }

    const foot = msgBar("ok", `Fetched ${Object.keys(g).length} live endpoints at ${new Date().toLocaleTimeString()}.`);
    root.appendChild(foot);
  },
};

/* ============================================================
   VIEW: P2 — Scoring
   ============================================================ */
const P2 = {
  presets: {
    "MICRO minimal": {
      application_id: "UI-DEMO-1", segment: "MICRO", operating_model: "G",
      facility: { product: "WORKING_CAPITAL_LINE", requested_amount: 8000 },
      model_maturity_stage: "SANDBOX",
    },
    "MICRO + cash flow": {
      application_id: "UI-DEMO-2", segment: "MICRO", operating_model: "G",
      facility: { product: "WORKING_CAPITAL_LINE", requested_amount: 8000 },
      model_maturity_stage: "SANDBOX",
      cash_flow: { avg_daily_inflow: 900.0, debt_service_obligation: 1200.0 },
    },
  },
  state: { result: null, requestError: null },

  async render() {
    const root = document.getElementById("panel-p2");
    root.replaceChildren(msgBar("info", "Loading P2…"));
    const g = await fetchMany([
      "/p2/v1/brr-pd-grid", "/p2/v1/category-weights/SMALL", "/p2/v1/category-weights/MICRO",
    ]);
    root.replaceChildren();
    root.appendChild(panelHead("P2 — AI/ML credit scoring & risk rating", "POST /p2/v1/score with a BorrowerApplication. Note: TERM_LOAN EAD/LGD is forward-compatible and not built this phase — use WORKING_CAPITAL_LINE. Every preset is a verified 200 body.", () => this.render()));

    // --- form ---
    const form = document.createElement("div");
    form.className = "p2-layout";
    const ctrl = el("div", "panel-block");
    ctrl.appendChild(el("h3", "", "BorrowerApplication"));
    const presetRow = el("div", "row-actions");
    for (const [name, value] of Object.entries(this.presets)) {
      const b = el("button", "btn small", name);
      b.addEventListener("click", () => { textarea.value = JSON.stringify(value, null, 2); this.state.result = null; renderResult(); });
      presetRow.appendChild(b);
    }
    ctrl.appendChild(presetRow);
    const textarea = document.createElement("textarea");
    textarea.className = "app-input";
    textarea.value = JSON.stringify(this.presets["MICRO + cash flow"], null, 2);
    ctrl.appendChild(textarea);
    const runRow = el("div", "row-actions");
    const runBtn = el("button", "btn primary", "Run score → POST /p2/v1/score");
    runBtn.addEventListener("click", async () => {
      runBtn.disabled = true;
      try {
        let parsed;
        try { parsed = JSON.parse(textarea.value); }
        catch (e) { this.state.requestError = "Invalid JSON: " + e.message; this.state.result = null; renderResult(); return; }
        const r = await api("/p2/v1/score", { method: "POST", body: parsed });
        this.state.requestError = r.ok ? null : (typeof r.data === "string" ? r.data : JSON.stringify(r.data));
        this.state.result = r.ok ? r.data : null;
        renderResult();
      } finally { runBtn.disabled = false; }
    });
    runRow.appendChild(runBtn);
    const note = el("div", "muted", "Response is the ScoringResult from the live engine over the seeded settings store.");
    ctrl.appendChild(runRow);
    ctrl.appendChild(note);
    form.appendChild(ctrl);

    // --- result panel ---
    const resultPanel = el("div", "panel-block");
    const resultHead = el("h3", "", "ScoringResult");
    const resultBox = el("div");
    resultPanel.appendChild(resultHead);
    resultPanel.appendChild(resultBox);
    form.appendChild(resultPanel);
    root.appendChild(form);

    const renderResult = () => {
      resultHead.innerHTML = "ScoringResult";
      resultBox.replaceChildren();
      if (this.state.requestError) {
        resultBox.appendChild(msgBar("bad", "Request failed"));
        resultBox.appendChild(el("pre", "err", this.state.requestError));
        return;
      }
      if (!this.state.result) { resultBox.appendChild(msgBar("info", "Run a score to see the result here.")); return; }
      const d = this.state.result;
      resultBox.appendChild(scorePanel(d));
      const det = el("p", "muted");
      const tgl = el("a", "", "Show full JSON ▸");
      tgl.style.cssText = "cursor:pointer;color:var(--accent)";
      tgl.addEventListener("click", () => {
        const raw = resultBox.querySelector("#p2-raw");
        if (raw) raw.remove(), tgl.textContent = "Show full JSON ▸";
        else { const pre = el("pre", "err", JSON.stringify(d, null, 2)); pre.id = "p2-raw"; resultBox.appendChild(pre); tgl.textContent = "Hide JSON ▾"; }
      });
      det.appendChild(tgl);
      det.className = "muted";
      resultBox.appendChild(det);
    };

    // --- BRR-PD grid + weights ---
    const grid = valueOr(g["/p2/v1/brr-pd-grid"], {});
    const gridRows = (grid.grid ? Object.entries(grid.grid) : []).map(([brr, [lo, hi]]) => ({
      BRR: brr, "PD lower": lo, "PD upper": hi,
    }));
    const wSmall = valueOr(g["/p2/v1/category-weights/SMALL"], {});
    const wMicro = valueOr(g["/p2/v1/category-weights/MICRO"], {});
    const wRows = ["SMALL", "MICRO"].map((seg) => {
      const w = seg === "SMALL" ? wSmall : wMicro;
      const r = { Segment: seg };
      for (const [k, v] of Object.entries(w)) r[k] = v;
      return r;
    });
    const ref = el("div");
    ref.appendChild(section("BRR→PD grid", [bodyHtml(renderTable(gridRows))], grid.version));
    ref.appendChild(section("Category weights", [bodyHtml(renderTable(wRows))]));
    root.appendChild(ref);

    renderResult();

    function scorePanel(d) {
      const r = d.rating || {};
      const cr = d.credit_risk || {};
      const pr = d.pricing || {};
      const dq = d.data_quality || {};
      const cs = (r.category_scores || []).map((c) => {
        const pct = Math.round((c.raw_score || 0) * 100);
        return `<tr><td>${esc(c.category)}</td><td>${fmt(c.weight)}</td>` +
               `<td><div style="background:#0b1220;border-radius:6px;height:10px;width:120px;display:inline-block">` +
               `<div style="width:${pct}%;height:100%;border-radius:6px;background:linear-gradient(90deg,#2f6fe0,#6d4df5)"></div></div>` +
               ` <span class="mono">${(c.raw_score || 0).toFixed(3)}</span></td></tr>`;
      }).join("");
      const cards = [
        ["BRR", pill("BRR " + fmt(r.brr), r.brr && r.brr <= 5 ? "ok" : (r.brr && r.brr <= 8 ? "warn" : "bad")), "rating band"],
        ["PD point", fmt(r.pd_point_estimate), "grid " + esc(r.pd_grid_version || "")],
        ["PD w/ MoC", fmt(r.pd_with_moc), "margin-of-conservatism +" + fmt(100 * (dq.moc_pd_uplift || 0)).padStart(1, "0") + "pp"],
        ["EAD", fmt(cr.ead), ""],
        ["LGD / MoC", `${fmt(cr.lgd)} ${cr.lgd_with_moc !== undefined && cr.lgd_with_moc !== cr.lgd ? "→ " + fmt(cr.lgd_with_moc) : ""}`, "with MoC uplift"],
        ["Expected loss", fmt(cr.expected_loss), "el_vs_budgeted " + (cr.el_vs_budgeted_loss || "")],
        ["Zone", pill(d.zone || "—", (d.zone || "").startsWith("AUTO") ? "ok" : (d.zone || "") === "MANUAL_REVIEW" ? "bad" : "warn"), "decisioning zone"],
        ["All-in rate", `${fmt(pr.all_in_rate_bps)} bps`, `base ${fmt(pr.base_rate_bps)} + risk ${fmt(pr.risk_premium_bps)}`],
      ];
      const p = d.packet || {};
      return (
        `<div class="card-grid">${cards.map(([t, v, s]) => `<div class="card"><h4>${esc(t)}</h4><div class="big">${v}</div>${s ? `<div class="sub">${s}</div>` : ""}</div>`).join("")}</div>` +
        `<div class="table-wrap" style="margin-top:10px"><table><thead><tr><th>Category</th><th>Weight</th><th>Raw score</th></tr></thead><tbody>${cs}</tbody></table></div>` +
        (p.application_id ? section("Output packet (decision → P3)", [bodyHtml(renderKeyValue(p))], p.status).outerHTML : "")
      );
    }
  },
};

/* ============================================================
   VIEW: P3 — Facilities / state machine
   ============================================================ */
const P3 = {
  state: { facilities: [], detail: null, sub: "audit", packet: null },

  async render() {
    const root = document.getElementById("panel-p3");
    root.replaceChildren(msgBar("info", "Loading P3…"));
    const g = await fetchMany([
      "/p3/api/v1/p3/facilities", "/p3/api/v1/p3/reconcile", "/p3/api/v1/p3/packets",
    ]);
    root.replaceChildren();
    root.appendChild(panelHead("P3 — Deterministic loan execution layer",
      "Facilities seeded to every persistable LoanState. Actions drive the real state machine through confirmed / workout-authorised P2 packets over the shared KvStore file.", () => this.render()));
    const { facilities, reconcile } = (() => {
      const fs = valueOr(g["/p3/api/v1/p3/facilities"], []) || [];
      const rc = valueOr(g["/p3/api/v1/p3/reconcile"], {}) || {};
      return { facilities: fs, reconcile: rc };
    })();
    const packets = valueOr(g["/p3/api/v1/p3/packets"], []) || [];
    this.state.facilities = facilities;
    this.state.packets = packets;

    const statusRow = el("div", "chip-row", "");
    statusRow.appendChild(el("span", "chip", `facilities <b>${facilities.length}</b>`));
    if (reconcile.within_tolerance !== undefined) {
      statusRow.appendChild(el("span", "chip",
        `reconcile <b>${pill(reconcile.within_tolerance ? "WITHIN" : "BREACH", reconcile.within_tolerance ? "ok" : "bad")}</b> discrepancy ${fmt(reconcile.discrepancy)}`));
    }
    root.appendChild(statusRow);
    root.appendChild(section("Execution controls", [this.buildActionPanel()], "live engine"));

    // facility table
    const table = el("div");
    table.appendChild(section("Facilities by state", [bodyHtml(renderTable(
      facilities.map((f) => ({
        facility_id: f.facility_id, state: f.state,
        collateral_count: f.collateral_count,
        veto_frozen: f.veto_frozen || "FALSE",
        updated_at: String(f.updated_at || "").slice(0, 19),
      }))
    ))], ""));
    table.appendChild(el("div", "muted", "Click a facility row for collateral detail below."));
    root.appendChild(table);

    // detail drawer
    const detailBox = el("div");
    root.appendChild(detailBox);
    table.querySelectorAll("tbody tr").forEach((tr, i) => {
      tr.classList.add("clickable");
      tr.addEventListener("click", async () => this.loadDetail(facilities[i].facility_id, detailBox));
    });

    // sub tabs
    const sub = el("div", "panel-block");
    const subNav = el("div", "inline", "");
    const subs = [["audit", "Audit / event log"], ["postings", "Postings"], ["ledger", "Core-banking ledger"], ["packets", "Confirmation packets"]];
    const box = el("div");
    sub.innerHTML = "<h3>Event log & postings</h3>";
    sub.appendChild(subNav);
    sub.appendChild(box);
    root.appendChild(sub);
    for (const [key, label] of subs) {
      const b = el("button", "btn small" + (key === this.state.sub ? " primary" : ""), label);
      b.addEventListener("click", async () => {
        this.state.sub = key;
        box.replaceChildren(msgBar("info", "Loading…"));
        const base = "/p3/api/v1/p3/" + (key === "packets" ? "packets" : key);
        const r = await api(base);
        box.replaceChildren(bodyHtml(renderValue(r.ok && Array.isArray(r.data) ? r.data : (r.ok ? [r.data] : []))));
        subNav.querySelectorAll("button").forEach((x, i) => x.className = "btn small" + (i === subs.findIndex((s) => s[0] === key) ? " primary" : ""));
      });
      subNav.appendChild(b);
    }
    // fire default sub on first paint
    box.replaceChildren(msgBar("info", "Loading…"));
    (async () => {
      const r = await api("/p3/api/v1/p3/" + this.state.sub);
      box.replaceChildren(bodyHtml(renderValue(r.ok && Array.isArray(r.data) ? r.data : (r.ok ? [r.data] : []))));
    })();
  },

  buildActionPanel() {
    const wrap = el("div");
    const row = el("div", "inline", "");
    const fac = el("select");
    for (const f of this.state.facilities) {
      const o = document.createElement("option"); o.value = f.facility_id; o.textContent = f.facility_id + " · " + f.state; fac.appendChild(o);
    }
    const newId = document.createElement("input");
    const action = el("select");
    const ACTION_PARAMS = {
      disburse: [["amount", 10000], ["currency", "USD"]],
      repayment: [["interest_amount", 100], ["principal_amount", 500], ["currency", "USD"]],
      recovery: [["recovered_amount", 1000], ["currency", "USD"]],
      "pledge-collateral": [["external_reference", "title-deed-UI"]],
      originate: [["facility_id", "FAC-UI-001"]],
    };
    const ops = ["disburse", "repayment", "mark-delinquent", "mark-default", "restructure", "recovery", "close", "pledge-collateral", "originate"];
    for (const o of ops) { const opt = document.createElement("option"); opt.value = o; opt.textContent = o; action.appendChild(opt); }

    const note = el("div", "muted", "Confirm packet is generated on-the-fly (APPROVED / officer-confirmed; workout-authorised for restructure · recovery · close).");
    const fieldBox = el("div", "inline", "");

    const field = (name, val) => {
      const d = el("div", "field"); d.innerHTML = `<label>${esc(name)}</label>`;
      const inp = document.createElement("input"); inp.value = String(val);
      d.appendChild(inp); fieldBox.appendChild(d); return inp;
    };
    const inputMap = {};
    for (const [n, v] of ACTION_PARAMS[action.value] || []) inputMap[n] = field(n, v);

    action.addEventListener("change", () => {
      fieldBox.replaceChildren();
      for (const [n, v] of ACTION_PARAMS[action.value] || []) inputMap[n] = field(n, v);
    });
    const go = el("button", "btn primary", "Execute → POST /p3/api/v1/p3/" + action.value);
    go.addEventListener("click", async () => {
      const name = action.value;
      const fid = name === "originate" ? (inputMap.facility_id ? inputMap.facility_id.value : "FAC-UI-001") : fac.value;
      const workout = ["restructure", "recovery", "close", "mark-default"].includes(name);
      const packet = {
        packet_id: "UI-" + Date.now().toString(36).toUpperCase(),
        facility_id: name === "originate" ? fid : fac.value,
        status: "APPROVED", maturity_stage: "SANDBOX", brr_pd_grid_version: "BRR-GRID-2026-04",
        collateral_track: "TRACK_1_CLASSICAL", packet_version: "v1", officer_confirmed: true,
        officer_id: "OFFICER-1", human_authorised_for_workout: workout,
        issued_at: new Date().toISOString(),
      };
      const qp = new URLSearchParams();
      if (name !== "originate") qp.set("facility_id", fac.value);
      for (const k of Object.keys(inputMap)) {
        if (k === "facility_id") continue;
        const v = inputMap[k].value;
        if (v === "" || v === undefined || v === null) continue;
        qp.set(k, /^-?\d+(\.\d+)?$/.test(v) ? Number(v) : v);
      }
      const qs = qp.toString();
      const url = "/p3/api/v1/p3/" + name + (qs ? "?" + qs : "");
      const r = await api(url, { method: "POST", body: packet });
      const out = el("div");
      out.replaceChildren(msgBar(r.ok ? "ok" : "bad", r.ok ? "OK — " + name : "HTTP " + r.status));
      if (!r.ok) out.appendChild(el("pre", "err", typeof r.data === "string" ? r.data : JSON.stringify(r.data, null, 2)));
      else out.appendChild(bodyHtml(`<details class="kv-group" style="margin-top:6px"><summary>response</summary><div class="inner">${renderKeyValue(r.data && typeof r.data === "object" ? r.data : { response: r.data })}</div></details>`));
      wrap.appendChild(out);
      await this.render();
    });

    const left = el("div", "field", ""); left.innerHTML = "<label>facility</label>";
    left.appendChild(fac);
    const actionF = el("div", "field", ""); actionF.innerHTML = "<label>life-cycle action</label>"; actionF.appendChild(action);
    row.append(left, actionF, fieldBox, go);
    wrap.appendChild(row);
    wrap.appendChild(note);
    return wrap;
  },

  async loadDetail(id, box) {
    box.replaceChildren(msgBar("info", "Loading detail…"));
    const r = await api("/p3/api/v1/p3/facilities/" + encodeURIComponent(id));
    const d = r.ok ? r.data : null;
    if (!d) { box.replaceChildren(msgBar("bad", "detail fetch failed")); return; }
    const h = el("div", "panel-block");
    h.innerHTML = `<h3>Facility detail · ${esc(id)} ${pill(d.state || "—")}</h3>`;
    h.appendChild(bodyHtml(renderKeyValue(d)));
    box.replaceChildren(h);
  },
};

/* ============================================================
   VIEW: P4 — Prudential
   ============================================================ */
const P4 = {
  async render() {
    const root = document.getElementById("panel-p4");
    root.replaceChildren(msgBar("info", "Loading P4…"));
    const E = {
      balances: "/p4/api/v1/p4/buffer/balances",
      capital: "/p4/api/v1/p4/capital/snapshot",
      adequacy: "/p4/api/v1/p4/pool/adequacy",
      ifrs9: "/p4/api/v1/p4/ifrs9",
      mode: "/p4/api/v1/p4/mode",
      veto: "/p4/api/v1/p4/veto/consult",
      events: "/p4/api/v1/p4/events",
    };
    const g = await fetchMany(Object.values(E));
    root.replaceChildren();
    root.appendChild(panelHead("P4 — Prudential capital, liquidity & loss absorption",
      "Sub-account buffer, Tier-D-vs-RWA floor, IFRS9 staging and the guarantee-pool adequacy all read live from the shared KvStore file; feeds write back through the same engine.", () => this.render()));

    const b = valueOr(g[E.balances], {});
    const cap = valueOr(g[E.capital], {});
    const aq = valueOr(g[E.adequacy], {});
    const mode = valueOr(g[E.mode], {});
    const vc = valueOr(g[E.veto], {});

    const kpis = [
      ["EL Pool", fmt(b.el_pool), "IFRS9 expected loss reserve"],
      ["ULA Buffer", fmt(b.ula_buffer), "unallocated loss absorption"],
      ["Liquidity Reserve", fmt(b.liquidity_reserve), "liquidity leg"],
      ["RP Pool", fmt(b.rp_pool), "reverse-restoration pool"],
      ["Tier D / RWA", `${(cap.tier_d_over_rwa * 100).toFixed(3)}%`,
        `floor ${((cap.tier_d_floor || 0) * 100).toFixed(0)}% · ` +
        (cap.tier_d_over_rwa >= (cap.tier_d_floor || 0.12) ? "OK" : "BELOW FLOOR")],
      ["Budgeted loss", (cap.budgeted_loss * 100).toFixed(0) + "%",
        "of RWA " + fmt(cap.rwa)],
      ["Guarantee pool", fmt(aq.received) + " / " + fmt(aq.required), aq.status],
      ["Mode", mode.mode + (mode.adaptive ? " (adaptive)" : ""), "conventional=" + mode.conventional],
    ];
    root.appendChild(section("Buffer & capital snapshot", [
      bodyHtml(`<div class="card-grid">${kpis.map(([t, v, s]) => `<div class="card"><h4>${esc(t)}</h4><div class="big">${v}</div><div class="sub">${s}</div></div>`).join("")}</div>`),
    ], vc.any_frozen ? "VETO FROZEN" : "CLEAR"));

    const ifrs = valueOr(g[E.ifrs9], {}) || {};
    const ifrsRows = Object.entries(ifrs).map(([fac, r]) => ({ facility_id: fac, stage: r.stage, ead: r.ead, el: r.el, ecl: r.ecl }));
    root.appendChild(section("IFRS9 staging (facility → EL pool)", [bodyHtml(renderTable(ifrsRows))]));

    const evts = valueOr(g[E.events], []) || [];
    root.appendChild(section("Pillar 3 → P4 event feed", [bodyHtml(renderValue(evts))]));

    // controls
    root.appendChild(this.buildControls(cap));
  },

  buildControls(cap) {
    const wrap = el("div", "panel-block");
    wrap.innerHTML = "<h3>Feed / control panel <span class='tag'>live writes to the shared KvStore — /ready re-asserts byte-identical restart</span></h3>";
    const grid = el("div", "p2-layout", "");

    const make = ({ title, path, query, fields, note }) => {
      const block = el("div");
      block.innerHTML = `<div class="field"><label style="font-weight:700;color:var(--ink)">${esc(title)}</label>` +
        (note ? `<div class="muted" style="font-size:11.5px">${esc(note)}</div>` : "") + "</div>";
      const bodyMap = {};
      const inputs = fields.map(([fname, def, ftype]) => {
        const d = el("div", "field");
        d.innerHTML = `<label>${esc(fname)}</label>`;
        const inp = document.createElement(ftype === "select" ? "select" : "input");
        if (ftype === "select") {
          for (const opt of def) { const o = document.createElement("option"); o.value = opt; o.textContent = opt; inp.appendChild(o); }
          if (def.includes("SMALL")) inp.value = "SMALL";
        } else {
          inp.value = String(def || "");
          if (ftype === "number") inp.type = "number";
        }
        bodyMap[fname] = inp;
        d.appendChild(inp);
        return d;
      });
      const btn = el("button", "btn primary", "Send");
      const out = el("div");
      btn.addEventListener("click", async () => {
        const payload = {};
        const qs = new URLSearchParams();
        for (const k of Object.keys(bodyMap)) {
          const el_ = bodyMap[k];
          let v = el_.type === "number" ? Number(el_.value) : el_.value;
          if (v === "" || (el_.type === "number" && isNaN(v))) continue;
          if (query.includes(k)) qs.set(k, v); else payload[k] = v;
        }
        const url = path + "?" + qs.toString();
        const r = await api(url, { method: "POST", body: Object.keys(payload).length ? payload : undefined });
        out.replaceChildren(msgBar(r.ok ? "ok" : "bad", r.ok ? "OK " + title : "HTTP " + r.status));
        if (!r.ok) out.appendChild(el("pre", "err", typeof r.data === "string" ? r.data : JSON.stringify(r.data, null, 2)));
        else if (r.data && typeof r.data === "object") out.appendChild(bodyHtml(`<details class="kv-group"><summary>response</summary><div class="inner">${renderKeyValue(r.data)}</div></details>`));
      });
      const row = el("div", "inline");
      inputs.forEach((i) => row.appendChild(i));
      row.appendChild(btn);
      block.appendChild(row);
      block.appendChild(out);
      return block;
    };

    const facilityOptions = [];
    const tierOptions = ["TierA", "TierB", "SeniorInstitutionalDebt", "TierC", "TierBFees", "TierD"];

    grid.appendChild(make({
      title: "Feed IFRS9 staging signal (P2 → P4)",
      path: "/p4/api/v1/p4/staging-signal", query: [], note: "migrates a facility into a new IFRS9 stage; bumps EL pool provisioning.",
      fields: [["facility_ref", "FAC-DEMO-001"], ["stage", 2, "number"], ["packet_ref", "UI-STG-1"]],
    }));
    grid.appendChild(make({
      title: "Publish required guarantee level (P4 admissibility)",
      path: "/p4/api/v1/p4/required-guarantee-level", query: [], note: "sets pool adequacy target; adequacy flips to shortfall/adequate.",
      fields: [["required_amount", 120000, "number"], ["revision_ref", "UI-RGL-1"]],
    }));
    grid.appendChild(make({
      title: "Feed risk packet (P2 BRR/PD/LGD/EAD)",
      path: "/p4/api/v1/p4/risk-packet", query: [],
      fields: [["facility_ref", "FAC-DEMO-001"], ["brr", 5, "number"], ["pd", 0.02, "number"],
               ["lgd", 0.75, "number"], ["ead", 180000, "number"], ["el", 2700, "number"]],
    }));
    grid.appendChild(make({
      title: "Veto — track 2 (facility-level prudential breach)",
      path: "/p4/api/v1/p4/veto/track2", query: ["facility_ref"], note: "freezes the facility on prudential grounds.",
      fields: [["facility_ref", "FAC-DEMO-001"], ["violates_policy", "true"]],
    }));
    grid.appendChild(make({
      title: "Lift track-1 portfolio freeze (governance review complete)",
      path: "/p4/api/v1/p4/veto/lift-track1", query: ["governance_ref"],
      fields: [["governance_ref", "RI-UI-CLEAR-1"]],
    }));
    grid.appendChild(make({
      title: "Activate Adaptive Mode (governance ruling)",
      path: "/p4/api/v1/p4/mode/activate", query: [], note: "SI-1 staged: needs a signed governance ruling.",
      fields: [["ruling_ref", "UI-RUL-1"], ["rule_type", "SI-1"], ["signed_by", "GovCom"], ["detail", "demo activate"]],
    }));
    grid.appendChild(make({
      title: "Fall back to Conventional Mode (permanent floor)",
      path: "/p4/api/v1/p4/mode/fallback", query: [],
      fields: [["ruling_ref", "UI-RUL-2"], ["rule_type", "SI-1"], ["signed_by", "GovCom"], ["detail", "demo fallback"]],
    }));
    grid.appendChild(make({
      title: "Submit RWA pledge (Pillar 5 gateway)",
      path: "/p4/api/v1/p4/pledge/submit", query: [], note: "tier is the full enum (TierA/TierB/SeniorInstitutionalDebt/TierC/TierBFees/TierD).",
      fields: [["submission_ref", "UI-PLD-1"], ["pledger_id", "PLEDGER-DEMO"],
               ["tier", tierOptions], ["amount", 60000, "number"], ["asset_class", "MSME_RWA"]],
    }));
    wrap.appendChild(grid);
    return wrap;
  },
};

/* ============================================================
   VIEW: Governance
   ============================================================ */
const Gov = {
  async render() {
    const root = document.getElementById("panel-gov");
    root.replaceChildren(msgBar("info", "Loading governance…"));
    const E = {
      canon: "/governance/api/v1/canon/current",
      lineage: "/governance/api/v1/canon/lineage",
      pillars: "/governance/api/v1/pillars",
      tiers: "/governance/api/v1/tiers",
      prot: "/governance/api/v1/tiers/protection-rules",
      gates: "/governance/api/v1/staging/gates",
      mode: "/governance/api/v1/staging/mode",
      stage: "/governance/api/v1/staging/stage",
      adaptive: "/governance/api/v1/staging/is-adaptive-active",
      pending: "/governance/api/v1/pending",
      pendSum: "/governance/api/v1/pending/summary",
      vetoes: "/governance/api/v1/vetoes",
      inter: "/governance/api/v1/interfaces",
      lexcats: "/governance/api/v1/lexicon/categories",
      lexx: "/governance/api/v1/lexicon/terms",
      cass: "/governance/api/v1/cass-stub",
    };
    const g = await fetchMany(Object.values(E));
    root.replaceChildren();
    root.appendChild(panelHead("Governance — canonical corpus & decision staging",
      "Operative canon, pillar boundary model, decision gates, interface rules and the pending register — all read live from the governance service.", () => this.render()));

    const canon = valueOr(g[E.canon], {});
    const mode = valueOr(g[E.mode], {});
    const stage = valueOr(g[E.stage], {});
    const adv = valueOr(g[E.adaptive], {});
    root.appendChild(section("Versions & staging", [
      bodyHtml(`<div class="card-grid">${[
        ["Current canon", pill(canon.version_number, "info"), esc(canon.name || "")],
        ["Status", pill(canon.status || "—"), "RI " + (canon.ratification_instrument || "—")],
        ["Ratified", esc(canon.ratified_at || "—"), ""],
        ["Staging mode", pill(mode.current_mode || "—"), esc(mode.fallback_guarantee || "")],
        ["Stage", `<span class="big">${fmt(stage.current_stage)}</span>`, "of gates G0–G3"],
        ["Adaptive active", pill(adv.adaptive ? "TRUE" : "FALSE", adv.adaptive ? "ok" : "mute"), ""],
      ].map(([t, v, s]) => `<div class="card"><h4>${esc(t)}</h4><div>${v}</div>${s ? `<div class="sub">${s}</div>` : ""}</div>`).join("")}</div>` +
        `<div class="muted" style="margin-top:10px;font-size:12px">${esc(canon.change_summary || "")}</div>`),
    ]));

    const lineage = valueOr(g[E.lineage], []) || [];
    root.appendChild(section("Canon lineage", [
      bodyHtml(renderTable(lineage.map((l) => ({ version_number: l.version_number, status: l.status, instrument: l.ratification_instrument || "—", ratified: l.ratified_at || "—", notes: l.lineage_notes || "" })))),
    ]));

    const tiers = valueOr(g[E.tiers], []) || [];
    const prot = valueOr(g[E.prot], []) || [];
    const tierLabel = (id) => { const t = tiers.find((x) => x.id === id); return t ? t.tier_label : id; };
    root.appendChild(section("Capital tiers (§4)", [
      bodyHtml(renderTable(tiers.map((t) => ({ tier: t.tier_label, name: t.tier_name, scope: t.model_scope, insurance: t.insurance_status || "—", section: t.canon_section_ref })))),
    ]));
    if (prot.length) root.appendChild(section("Protection rules", [
      bodyHtml(renderTable(prot.map((p) => ({ from: tierLabel(p.source_tier_id), to: tierLabel(p.target_tier_id), direction: p.direction, note: p.description })))),
    ]));

    const gates = valueOr(g[E.gates], []) || [];
    root.appendChild(section("Decision gates G0–G3 (Annex B, SI-1)", [
      bodyHtml(renderTable(gates.map((x) => ({ gate: x.gate_label, status: x.status, criteria: x.criteria, cleared_by: x.cleared_by || "—" })))),
    ]));

    const inter = valueOr(g[E.inter], []) || [];
    root.appendChild(section("Interface rules 6.1–6.7", [
      bodyHtml(renderTable(inter.map((x) => ({
        rule: x.rule_number, name: x.name, direction: x.direction,
        bypasses_pillar3: x.bypasses_pillar3 ? pill("TRUE", "warn") : pill("FALSE", "ok"),
        decides: x.decides_who || "—", executes: x.executes_who || "—", section: x.canon_section_ref,
      })))),
    ]));

    const pendings = valueOr(g[E.pending], []) || [];
    const pendSum = valueOr(g[E.pendSum], {}) || {};
    root.appendChild(section("Pending register (" + fmt(pendSum.open) + " open)", [
      bodyHtml(`<div class="chip-row">${["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((p) => el("span", "chip", `${p} <b>${fmt(pendSum.by_priority?.[p] || 0)}</b>`).outerHTML).join("")}</div>`),
      bodyHtml(renderTable(pendings.map((x) => ({ item: x.item_number, priority: x.priority, category: x.category, status: x.status, title: x.title, section: x.registered_in_canon })))),
    ]));

    const vetoes = valueOr(g[E.vetoes], []) || [];
    root.appendChild(section("Prudential veto log (P4)", [
      bodyHtml(vetoes.length ? renderTable(vetoes) : `<div class="empty">No vetoes recorded — track-1/track-2 clear. (consult: ${pill("CLEAR", "ok")})</div>`),
    ]));

    const cats = valueOr(g[E.lexcats], []) || [];
    const terms = valueOr(g[E.lexx], []) || [];
    root.appendChild(section("Master Lexicon (Annex A)", [
      bodyHtml(`<div class="chip-row">${cats.map((c) => el("span", "chip", `${esc(c.name)} <b>${esc(c.annex_ref)}</b>`).outerHTML).join("")}</div>`),
      bodyHtml(renderTable(terms.slice(0, 200))),
    ]));

    const cass = valueOr(g[E.cass], {});
    root.appendChild(section("CASS interface stub CIS-1", [
      bodyHtml(renderKeyValue(cass)),
    ], cass.version));
  },
};

/* ============================================================
   Boot
   ============================================================ */
const RENDERERS = { dashboard: Dashboard, p2: P2, p3: P3, p4: P4, gov: Gov };

function bindTab() {
  document.getElementById("tabs").addEventListener("click", (e) => {
    const btn = e.target.closest(".tab");
    if (!btn) return;
    const tab = btn.dataset.tab;
    document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b === btn));
    const fn = RENDERERS[tab];
    if (fn) fn.render();
  });
}

async function headerStatus() {
  const chips = document.getElementById("header-chips");
  const [h, r] = await Promise.all([api("/health"), api("/ready")]);
  const ver = h.ok && h.data ? h.data.version : "—";
  document.getElementById("app-version").textContent = "v" + ver;
  const readyP3 = r.ok && r.data && r.data.checks && r.data.checks.p3_restart_ok;
  const readyP4 = r.ok && r.data && r.data.checks && r.data.checks.p4_restart_ok;
  chips.innerHTML =
    `<span class="chip">health <b>${h.ok ? (h.data.status || "ok") : "down"}</b></span>` +
    `<span class="chip">p3 restart <b>${pill(readyP3 ? "TRUE" : "FALSE", readyP3 ? "ok" : "bad")}</b></span>` +
    `<span class="chip">p4 restart <b>${pill(readyP4 ? "TRUE" : "FALSE", readyP4 ? "ok" : "bad")}</b></span>`;
}

async function start() {
  bindTab();
  headerStatus();
  setInterval(headerStatus, 30000);
  const foot = document.getElementById("foot-note");
  foot.textContent = "Demo data seeded via bank.orchestrator.demo.seed into ./data/orchestrator.db — one KvStore file; /ready re-opens it and asserts a byte-identical restart.";
  await RENDERERS.dashboard.render();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
else start();