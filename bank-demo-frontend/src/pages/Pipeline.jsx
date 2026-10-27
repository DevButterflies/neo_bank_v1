import { useState } from "react";
import { useDemoStatePoll } from "../data/hooks";
import { KanbanColumn } from "../components/pipeline/KanbanColumn";
import { CandidateDrawer } from "../components/pipeline/CandidateDrawer";
import { ImportMenu } from "../components/pipeline/ImportMenu";

export default function Pipeline() {
  const { data: state } = useDemoStatePoll();
  const [selectedId, setSelectedId] = useState(null);
  const candidates = state?.candidates || [];
  const selected = candidates.find((c) => c.id === selectedId) ?? null;

  const byStatus = (statuses) => candidates.filter((c) => statuses.includes(c.status));

  return (
    <div className="space-y-6 rise-in">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-head text-xl font-medium">Pipeline</h1>
          <p className="text-sm text-muted mt-0.5">Intake → real credit score → manual officer decision → disbursement.</p>
        </div>
        <ImportMenu />
      </div>

      <div className="flex gap-5 overflow-x-auto pb-2">
        <KanbanColumn title="New" candidates={byStatus(["new"])} onSelect={(c) => setSelectedId(c.id)} tone="text" />
        <KanbanColumn title="Scored" candidates={byStatus(["scored"])} onSelect={(c) => setSelectedId(c.id)} tone="amber" />
        <KanbanColumn title="Approved" candidates={byStatus(["approved", "disbursing"])} onSelect={(c) => setSelectedId(c.id)} tone="ledger" />
        <KanbanColumn title="Disbursed" candidates={byStatus(["disbursed"])} onSelect={(c) => setSelectedId(c.id)} tone="ledger" />
        <KanbanColumn
          title="Delinquent / defaulted"
          candidates={byStatus(["delinquent", "defaulted"])}
          onSelect={(c) => setSelectedId(c.id)}
          tone="danger"
        />
        <KanbanColumn title="Closed / rejected" candidates={byStatus(["closed", "rejected"])} onSelect={(c) => setSelectedId(c.id)} tone="text" />
      </div>

      <CandidateDrawer candidate={selected} onClose={() => setSelectedId(null)} />
    </div>
  );
}
