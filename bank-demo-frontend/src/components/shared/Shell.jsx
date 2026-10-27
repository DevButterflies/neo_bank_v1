import { NavLink, Outlet } from "react-router-dom";
import { ReadyBadge } from "./ReadyBadge";
import { VetoBanner } from "./VetoBanner";
import { MockModeBanner } from "./MockModeBanner";
import { TickControl } from "./TickControl";
import { useCanon, useMode } from "../../data/hooks";

const NAV = [
  { to: "/", label: "Control tower", icon: "◧" },
  { to: "/pipeline", label: "Pipeline", icon: "◫" },
  { to: "/loans", label: "Loans", icon: "☰" },
  { to: "/bilan", label: "Bilan", icon: "◨" },
];

export function Shell() {
  return (
    <div className="min-h-screen flex">
      <aside className="w-56 shrink-0 border-r border-line bg-panel/60 flex flex-col">
        <div className="px-5 py-5 border-b border-line">
          <div className="font-head font-semibold text-lg tracking-tight">Ledger</div>
          <div className="text-[11px] text-faint mt-0.5">MSME credit control tower</div>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-sm text-sm transition ${
                  isActive ? "bg-ledger/10 text-ledger" : "text-muted hover:text-text hover:bg-raised"
                }`
              }
            >
              <span className="w-4 text-center">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <CanonFooter />
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <MockModeBanner />
        <VetoBanner />
        <header className="h-14 shrink-0 border-b border-line px-6 flex items-center justify-between">
          <ModeStrip />
          <ReadyBadge />
        </header>
        <main className="flex-1 p-6 overflow-y-auto scrollbar-thin">
          <Outlet />
        </main>
      </div>
      <TickControl />
    </div>
  );
}

function ModeStrip() {
  const { data: mode } = useMode();
  return (
    <div className="flex items-center gap-2 text-xs text-muted">
      <span className="text-faint">Mode</span>
      <span className="font-mono text-text">{mode?.mode ?? "CONVENTIONAL"}</span>
      {!mode?.adaptive && <span className="text-faint">· conventional is the permanent floor</span>}
    </div>
  );
}

function CanonFooter() {
  const { data: canon } = useCanon();
  return (
    <div className="px-5 py-4 border-t border-line text-[11px] text-faint">
      <div className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-ledger" />
        Canon {canon?.version_number ?? "V3.4"} {canon?.status ?? "RATIFIED"}
      </div>
    </div>
  );
}
