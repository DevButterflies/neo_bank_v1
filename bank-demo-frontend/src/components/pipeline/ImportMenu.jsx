import { useRef, useState } from "react";
import { useDemoProfiles, useCreateCandidate, useImportCandidate, useSeedDemo } from "../../data/hooks";
import { formatMoney } from "../../utils/codec";

export function ImportMenu() {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState(null); // "seed" | "upload" | "manual"
  const { data: profiles } = useDemoProfiles();
  const seedDemo = useSeedDemo();
  const importCandidate = useImportCandidate();
  const fileRef = useRef(null);

  async function handleFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    try {
      const json = JSON.parse(text);
      await importCandidate.mutateAsync(json);
      setOpen(false);
    } catch (err) {
      alert(`Could not import file: ${err.message}`);
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="bg-ledger text-ink text-sm font-medium px-4 py-2 rounded-sm hover:bg-ledger/90 transition"
      >
        + Bring in a candidate
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 bg-raised border border-line rounded-md shadow-2xl shadow-black/40 z-30 p-2">
          <MenuButton active={mode === "seed"} onClick={() => setMode("seed")} label="Load a demo profile" desc="6 deterministic seeded borrowers" />
          <MenuButton active={mode === "upload"} onClick={() => { setMode("upload"); fileRef.current?.click(); }} label="Upload a candidate file" desc="Exported carrier JSON" />
          <MenuButton active={mode === "manual"} onClick={() => setMode("manual")} label="New applicant" desc="Manual intake — thin file, routes to review" />

          <input ref={fileRef} type="file" accept="application/json" className="hidden" onChange={handleFile} />

          {mode === "seed" && (
            <div className="mt-2 border-t border-line pt-2 space-y-1 max-h-64 overflow-y-auto scrollbar-thin">
              {(profiles || []).map((p) => (
                <button
                  key={p.id}
                  onClick={async () => {
                    await seedDemo.mutateAsync();
                    setOpen(false);
                  }}
                  className="w-full text-left px-3 py-2 rounded-sm hover:bg-panel text-xs"
                >
                  <div className="text-text capitalize">{p.id} · {p.data_tier} file</div>
                  <div className="text-faint">
                    {p.outcome} · {formatMoney(p.requested_amount)}
                  </div>
                </button>
              ))}
              <div className="text-[10px] text-faint px-3 pt-1">Loads all six seeded profiles at once (idempotent).</div>
            </div>
          )}

          {mode === "manual" && <ManualIntakeForm onDone={() => setOpen(false)} />}
        </div>
      )}
    </div>
  );
}

function MenuButton({ active, onClick, label, desc }) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2.5 rounded-sm transition ${active ? "bg-panel" : "hover:bg-panel"}`}
    >
      <div className="text-sm text-text">{label}</div>
      <div className="text-[11px] text-faint">{desc}</div>
    </button>
  );
}

function ManualIntakeForm({ onDone }) {
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    city: "Muscat",
    requested_amount: 10000,
    requested_tenure_months: 12,
    monthly_salary: 1500,
  });
  const create = useCreateCandidate();

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  return (
    <div className="mt-2 border-t border-line pt-3 space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <Field label="First name" value={form.first_name} onChange={(v) => set("first_name", v)} />
        <Field label="Last name" value={form.last_name} onChange={(v) => set("last_name", v)} />
      </div>
      <Field label="City" value={form.city} onChange={(v) => set("city", v)} />
      <div className="grid grid-cols-2 gap-2">
        <Field label="Amount" type="number" value={form.requested_amount} onChange={(v) => set("requested_amount", Number(v))} />
        <Field label="Tenure (mo)" type="number" value={form.requested_tenure_months} onChange={(v) => set("requested_tenure_months", Number(v))} />
      </div>
      <Field label="Monthly salary" type="number" value={form.monthly_salary} onChange={(v) => set("monthly_salary", Number(v))} />
      <button
        onClick={async () => {
          await create.mutateAsync(form);
          onDone();
        }}
        disabled={create.isPending || !form.first_name || !form.last_name}
        className="w-full bg-ledger text-ink text-sm font-medium py-2 rounded-sm hover:bg-ledger/90 disabled:opacity-50 transition mt-1"
      >
        {create.isPending ? "Creating…" : "Create candidate"}
      </button>
      <div className="text-[10px] text-faint">
        Form-built candidates get a thin application (KYC + mobile-money only) — they'll deterministically land in
        manual review after scoring.
      </div>
    </div>
  );
}

function Field({ label, value, onChange, type = "text" }) {
  return (
    <label className="block">
      <div className="text-[10px] text-faint mb-1">{label}</div>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-ink border border-line rounded-sm px-2.5 py-1.5 text-xs text-text focus:outline-none focus:border-ledger/50"
      />
    </label>
  );
}
