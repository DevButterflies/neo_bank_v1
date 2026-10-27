import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { X } from "lucide-react";

interface Props {
  title: string;
  subtitle?: ReactNode;
  onClose(): void;
  children: ReactNode;
}

/** The side sheet every area uses: scrim, Esc to close, focus moves in on open and back to the opener on close. */
export function Sheet({ title, subtitle, onClose, children }: Props) {
  const heading = useRef<HTMLHeadingElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    heading.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && closeRef.current();
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      requestAnimationFrame(() => opener?.focus());
    };
  }, []);

  return (
    <div className="sheet-layer">
      <div className="scrim sheet-scrim" onClick={onClose} aria-hidden="true" />
      <aside className="panel sheet" aria-labelledby="sheet-title">
        <div className="panel-head">
          <div>
            <h2 id="sheet-title" ref={heading} tabIndex={-1}>
              {title}
            </h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            <X size={18} aria-hidden="true" />
          </button>
        </div>
        <div className="panel-body">{children}</div>
      </aside>
    </div>
  );
}

/** One-line error box for a refused action, explaining a 409 rather than offering a retry. */
export function ActionError({ error }: { error: { status: number; detail: string } | null }) {
  if (!error) return null;
  return (
    <div className="error" role="alert">
      <b>{error.status === 409 ? "Blocked. " : "Not done. "}</b>
      {error.detail}
    </div>
  );
}
