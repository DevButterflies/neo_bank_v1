import { useDemoStatePoll } from "../data/hooks";
import { Panel } from "../components/shared/Atoms";
import { FacilityTable } from "../components/loans/FacilityTable";

export default function Loans() {
  const { data: state } = useDemoStatePoll();
  const candidates = state?.candidates || [];

  return (
    <div className="space-y-6 rise-in">
      <div>
        <h1 className="font-head text-xl font-medium">Loans</h1>
        <p className="text-sm text-muted mt-0.5">Every originated facility, its live balance, and its lifecycle state.</p>
      </div>
      <Panel>
        <FacilityTable candidates={candidates} />
      </Panel>
    </div>
  );
}
