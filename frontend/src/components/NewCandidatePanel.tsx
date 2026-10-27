import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { X } from "lucide-react";
import { ApiError } from "../api/client";
import type { Candidate, CandidateCreate, EmployerType } from "../api/types";
import { PRODUCT_LABELS } from "../lib/format";
import { useBoard } from "../state/board";

type Errors = Partial<Record<keyof CandidateCreate, string>>;

const EMPLOYER_TYPES: { value: EmployerType; label: string }[] = [
  { value: "self_employed", label: "Self-employed" },
  { value: "private", label: "Private company" },
  { value: "government", label: "Government" },
  { value: "military", label: "Military" },
];

function validate(f: FormData): { body?: CandidateCreate; errors: Errors } {
  const s = (k: string) => String(f.get(k) ?? "").trim();
  const n = (k: string) => Number(s(k));
  const errors: Errors = {};
  if (!s("first_name")) errors.first_name = "Enter the first name.";
  if (!s("last_name")) errors.last_name = "Enter the last name.";
  if (!(n("monthly_salary") > 0)) errors.monthly_salary = "Enter a monthly income above 0.";
  if (!(n("requested_amount") > 0)) errors.requested_amount = "Enter an amount above 0.";
  if (!Number.isInteger(n("requested_tenure_months")) || n("requested_tenure_months") < 1)
    errors.requested_tenure_months = "Enter a whole number of months.";
  if (s("age") && (n("age") < 18 || n("age") > 100)) errors.age = "Age must be between 18 and 100.";
  if (Object.keys(errors).length) return { errors };
  return {
    errors,
    body: {
      first_name: s("first_name"),
      last_name: s("last_name"),
      gender: (s("gender") || "male") as CandidateCreate["gender"],
      age: n("age") || 0,
      national_id: s("national_id") || null,
      phone: s("phone") || null,
      city: s("city") || "Muscat",
      employer_name: s("employer_name") || null,
      employer_type: (s("employer_type") || null) as EmployerType | null,
      employment_years: n("employment_years") || 1,
      job_title: s("job_title") || null,
      monthly_salary: n("monthly_salary"),
      product: s("product"),
      requested_amount: n("requested_amount"),
      requested_tenure_months: n("requested_tenure_months"),
    },
  };
}

function Field({
  name,
  label,
  errors,
  hint,
  ...input
}: { name: keyof CandidateCreate; label: string; errors: Errors; hint?: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  const err = errors[name];
  return (
    <div className="field">
      <label htmlFor={name}>{label}</label>
      <input id={name} name={name} aria-invalid={!!err} aria-describedby={err ? `${name}-err` : undefined} {...input} />
      {err ? (
        <span className="field-error" id={`${name}-err`}>
          {err}
        </span>
      ) : (
        hint && <span className="hint">{hint}</span>
      )}
    </div>
  );
}

export function NewCandidatePanel({ onClose, onCreated }: { onClose(): void; onCreated(c: Candidate): void }) {
  const { create } = useBoard();
  const [errors, setErrors] = useState<Errors>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => document.getElementById("first_name")?.focus(), []);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const { body, errors } = validate(new FormData(e.currentTarget));
    setErrors(errors);
    if (!body) return;
    setBusy(true);
    setFailure(null);
    try {
      onCreated(await create(body));
    } catch (err) {
      setFailure(err instanceof ApiError ? err.detail : "The API could not be reached. Check that the backend is running.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <aside className="panel" aria-labelledby="new-title">
      <div className="panel-head">
        <div>
          <h2 id="new-title">New candidate</h2>
          <p>Joins the line at New; submit it to have Pillar 2 score it.</p>
        </div>
        <button className="icon-btn" onClick={onClose} aria-label="Close form">
          <X size={18} aria-hidden="true" />
        </button>
      </div>
      <form className="panel-body" onSubmit={onSubmit} noValidate>
        <div className="grid-2">
          <Field name="first_name" label="First name" errors={errors} autoComplete="off" />
          <Field name="last_name" label="Last name" errors={errors} autoComplete="off" />
        </div>
        <div className="grid-2">
          <Field name="age" label="Age" errors={errors} type="number" inputMode="numeric" />
          <Field name="city" label="City" errors={errors} placeholder="Muscat" />
        </div>
        <div className="grid-2">
          <Field name="national_id" label="National ID" errors={errors} />
          <Field name="phone" label="Phone" errors={errors} type="tel" />
        </div>
        <Field name="employer_name" label="Business or employer" errors={errors} />
        <div className="grid-2">
          <div className="field">
            <label htmlFor="employer_type">Employer type</label>
            <select id="employer_type" name="employer_type" defaultValue="self_employed">
              {EMPLOYER_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>
          <Field name="employment_years" label="Years in business" errors={errors} type="number" step="0.5" defaultValue={1} />
        </div>
        <Field name="monthly_salary" label="Monthly income (USD)" errors={errors} type="number" inputMode="decimal" />
        <div className="field">
          <label htmlFor="product">Product</label>
          <select id="product" name="product" defaultValue="working_capital_line">
            {Object.entries(PRODUCT_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="grid-2">
          <Field name="requested_amount" label="Amount (USD)" errors={errors} type="number" inputMode="decimal" />
          <Field name="requested_tenure_months" label="Tenure (months)" errors={errors} type="number" defaultValue={12} />
        </div>
        {failure && (
          <div className="error" role="alert">
            <b>Not created. </b>
            {failure}
          </div>
        )}
        <div className="actions">
          <button className="btn btn-primary" type="submit" disabled={busy}>
            Create candidate
          </button>
          <button className="btn" type="button" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </aside>
  );
}
