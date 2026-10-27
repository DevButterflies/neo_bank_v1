import { useCallback } from "react";
import { useDemoStatePoll, useLiftTrack1, useVetoLog } from "../../data/hooks";

const TRIGGER_LABELS = {
  tier_d_over_rwa: "Tier D / RWA below floor",
  portfolio_el: "Portfolio EL above budgeted loss ratio",
  sector_concentration: "Sector concentration",
  guarantee_pool_concentration: "Guarantee-pool concentration",
  guarantees_granted_received_ratio: "Guarantees granted / received ratio",
  liquidity_buffer_below_minimum: "Liquidity buffer below minimum",
  cass_severe_pre_resolution: "CASS severe pre-resolution zone",
};

function fmtRatio(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function fmtSince(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function VetoBanner() {
  const { data: state } = useDemoStatePoll();
  const { data: vetoes } = useVetoLog();
  const lift = useLiftTrack1();

  const p4 = state?.p4 || {};
  const frozen = !!p4.track1_status && p4.track1_status !== "clear";
  const openVetoes = (vetoes || []).filter((v) => v.governance_review_status === "OPEN");

  const breached = p4.breached_triggers || [];
  const unmonitored = p4.unmonitored_triggers || [];
  const standing = p4.standing_breached_triggers || [];
  const frozenSince = fmtSince(p4.frozen_since);
  const bookClean = frozen && breached.length === 0;
  const freezeDetails = p4.freeze_details || {};

  const handleLift = useCallback(() => {
    const ref = `GOV-DEMO-${Date.now()}`;
    lift.mutate(ref);
  }, [lift]);

  if (!frozen && openVetoes.length === 0) return null;

  return (
    <div className="bg-danger/10 border-b border-danger/40 px-6 py-3 text-sm text-danger">
      <div className="flex items-center gap-3">
        <span className="w-1.5 h-1.5 rounded-full bg-danger pulse-dot shrink-0" />
        <span className="font-medium">
          Origination frozen — Track 1 portfolio veto is active. Governance review required before restart.
          {openVetoes.length > 0 && ` (${openVetoes.length} open veto event${openVetoes.length > 1 ? "s" : ""})`}
        </span>
      </div>

      {frozen && (
        <div className="mt-2 space-y-1.5 text-xs text-danger/90">
          {bookClean && (
            <div className="text-danger">
              Book is now clean — all live metrics sit within their prudential bounds. The freeze is held
              pending a governance review, not because anything is breaching right now.
            </div>
          )}
          <div>
            Portfolio EL&nbsp;{" "}
            <span className="font-semibold text-danger">{fmtRatio(p4.portfolio_el_ratio)}</span>
            &nbsp;/&nbsp;budget&nbsp;
            <span className="font-semibold">{fmtRatio(p4.budgeted_loss_ratio)}</span>
            {p4.budgeted_loss_ratio > 0 && (
              <span className="opacity-70">
                {" "}
                (headroom {fmtRatio(p4.budgeted_loss_ratio - (p4.portfolio_el_ratio ?? 0))})
              </span>
            )}
            {p4.portfolio_el_ratio === 0 && <span className="opacity-70"> — debt-free book</span>}
          </div>
          {standing.length > 0 && (
            <div>
              Freeze held for:{" "}
              <span className="font-semibold">
                {standing.map((t) => TRIGGER_LABELS[t] || t).join(", ")}
              </span>
              {frozenSince && <span className="opacity-70"> (since {frozenSince})</span>}
            </div>
          )}
          {standing.length > 0 && (
            <div className="opacity-80">
              Frozen at:{" "}
              {standing.map((t) => {
                const d = freezeDetails[t];
                if (!d) return null;
                if (t === "portfolio_el")
                  return (
                    <span key={t}>
                      EL {fmtRatio(d.portfolio_el)} vs budget {fmtRatio(d.budgeted_loss_ratio)}
                      {typeof d.ead_book === "number" && d.ead_book > 0 && (
                        <>
                          {" "}
                          (exposure ${Number(d.ead_book).toLocaleString()}, EL ${Number(d.el_book).toLocaleString()})
                        </>
                      )}
                    </span>
                  );
                if (t === "tier_d_over_rwa")
                  return (
                    <span key={t}>
                      Tier D/RWA {fmtRatio(d.tier_d_over_rwa)} vs floor {fmtRatio(d.tier_d_floor)}
                    </span>
                  );
                return <span key={t}>{(d.portfolio_el ?? d.tier_d_over_rwa ?? JSON.stringify(d))}</span>;
              })}
            </div>
          )}
          {breached.length > 0 && (
            <div className="opacity-80">
              Currently breached: {breached.map((t) => TRIGGER_LABELS[t] || t).join(", ")}
            </div>
          )}
          {unmonitored.length > 0 && (
            <div className="opacity-75">
              Unmonitored (limit not configured): {unmonitored.map((t) => TRIGGER_LABELS[t] || t).join(", ")}
            </div>
          )}
        </div>
      )}

      <div className="mt-2.5 flex items-center gap-3">
        <button
          onClick={handleLift}
          disabled={lift.isPending}
          className="bg-danger text-white text-xs font-medium px-3.5 py-1.5 rounded-sm hover:bg-danger/90 disabled:opacity-50 transition"
        >
          {lift.isPending ? "Reviewing…" : "Governance review & release Track 1"}
        </button>
        {lift.isError && (
          <span className="text-xs text-danger">
            Release failed — {lift.error?.message || "try again"}
          </span>
        )}
        {lift.isSuccess && <span className="text-xs text-muted">Track 1 released.</span>}
      </div>
    </div>
  );
}