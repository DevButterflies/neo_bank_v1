import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { FastForward, RotateCcw } from "lucide-react";
import { useBoard } from "../state/board";

const AREAS = [
  { to: "/", label: "Pipeline", end: true },
  { to: "/facilities", label: "Facilities" },
  { to: "/prudential", label: "Prudential" },
  { to: "/bilan", label: "Bilan" },
  { to: "/governance", label: "Governance" },
];

const SOURCE_LABEL = {
  connecting: "Connecting…",
  live: "Live API",
  demo: "Demo data · API offline",
};

const SOURCE_SHORT = { connecting: "Connecting…", live: "Live", demo: "Demo data" };

export function TopBar() {
  const { board, source, advanceMonth, reset } = useBoard();
  const [busy, setBusy] = useState(false);
  const [armed, setArmed] = useState(false);

  // a reset needs a second click within a few seconds
  useEffect(() => {
    if (!armed) return;
    const t = window.setTimeout(() => setArmed(false), 4000);
    return () => window.clearTimeout(t);
  }, [armed]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    try {
      await fn();
    } finally {
      setBusy(false);
    }
  };

  return (
    <header className="topbar">
      <NavLink to="/" className="brand">
        NeoBank <span>Admin</span>
      </NavLink>
      <nav className="nav" aria-label="Areas">
        {AREAS.map((a) => (
          <NavLink key={a.to} to={a.to} end={a.end}>
            {a.label}
          </NavLink>
        ))}
      </nav>
      <div className="topbar-demo">
        <span className="source" data-source={source} title={SOURCE_LABEL[source]}>
          <i aria-hidden="true" />
          <span className="source-long">{SOURCE_LABEL[source]}</span>
          <span className="source-short">{SOURCE_SHORT[source]}</span>
        </span>
        {board && <span className="month">Month {board.month}</span>}
        <button
          className="btn btn-small"
          disabled={!board || busy}
          onClick={() => run(advanceMonth)}
          title="Move every disbursed facility one month along its payment behaviour"
        >
          <FastForward size={15} aria-hidden="true" />
          <span>
            Advance<span className="hide-narrow"> month</span>
          </span>
        </button>
        <button
          className="btn btn-small"
          data-armed={armed}
          disabled={!board || busy}
          onClick={() => {
            if (!armed) return setArmed(true);
            setArmed(false);
            void run(reset);
          }}
        >
          <RotateCcw size={15} aria-hidden="true" />
          {armed ? "Confirm reset" : "Reset"}
        </button>
      </div>
    </header>
  );
}
