import type { CSSProperties } from "react";
import type { DecisioningZone } from "../api/types";
import { ZONES } from "../lib/format";

export function ZoneMark({ zone }: { zone: DecisioningZone | null }) {
  if (!zone) return null;
  const z = ZONES[zone];
  return (
    <span className="zone" style={{ "--c": z.color } as CSSProperties}>
      <i aria-hidden="true" />
      {z.label}
    </span>
  );
}
