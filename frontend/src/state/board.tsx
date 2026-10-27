import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { ApiError, api, loadBoard, subscribeBoard } from "../api/client";
import { fixtureBoard, fixtureCandidate, fixtureScore } from "../api/fixtures";
import type { BoardSnapshot, Candidate, CandidateCreate } from "../api/types";

export type Source = "connecting" | "live" | "demo";

interface BoardContextValue {
  board: BoardSnapshot | null;
  source: Source;
  /** Candidate ids that changed on the last refresh, for a one-time flash. */
  moved: Set<string>;
  submit(id: string): Promise<void>;
  decide(id: string, approve: boolean, note: string): Promise<void>;
  disburse(id: string): Promise<void>;
  create(body: CandidateCreate): Promise<Candidate>;
  advanceMonth(): Promise<void>;
  reset(): Promise<void>;
}

const BoardContext = createContext<BoardContextValue | null>(null);

const OFFICER = { officer_id: "ADMIN-1", officer_name: "Admin" };

function changedIds(prev: BoardSnapshot | null, next: BoardSnapshot): Set<string> {
  if (!prev) return new Set();
  const before = new Map(prev.candidates.map((c) => [c.id, c.status]));
  return new Set(next.candidates.filter((c) => before.get(c.id) !== c.status).map((c) => c.id));
}

export function BoardProvider({ children }: { children: ReactNode }) {
  const [board, setBoard] = useState<BoardSnapshot | null>(null);
  const [source, setSource] = useState<Source>("connecting");
  const [moved, setMoved] = useState<Set<string>>(new Set());
  const boardRef = useRef(board);
  boardRef.current = board;

  const apply = useCallback((next: BoardSnapshot) => {
    setMoved(changedIds(boardRef.current, next));
    setBoard(next);
  }, []);

  const refresh = useCallback(async () => {
    apply(await loadBoard());
  }, [apply]);

  useEffect(() => {
    let unsubscribe = () => {};
    let cancelled = false;
    loadBoard()
      .then((snapshot) => {
        if (cancelled) return;
        setSource("live");
        setBoard(snapshot);
        unsubscribe = subscribeBoard(() => void refresh().catch(() => {}));
      })
      .catch(() => {
        if (cancelled) return;
        setSource("demo");
        setBoard(fixtureBoard());
      });
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, [refresh]);

  /** Offline mutation helper: applies a change to one candidate. */
  const patch = useCallback(
    (id: string, change: (c: Candidate, b: BoardSnapshot) => Partial<Candidate>) => {
      const b = boardRef.current;
      if (!b) return;
      apply({
        ...b,
        candidates: b.candidates.map((c) =>
          c.id === id ? { ...c, ...change(c, b), updated_at: new Date().toISOString() } : c,
        ),
      });
    },
    [apply],
  );

  const value = useMemo<BoardContextValue>(() => {
    const live = source === "live";
    const now = () => new Date().toISOString();
    return {
      board,
      source,
      moved,
      async submit(id) {
        if (live) return void (await api.submit(id), await refresh());
        patch(id, (c) => {
          const s = fixtureScore(c);
          return { status: "submitted", submitted_at: now(), scored_at: now(), p2_brr: s.brr, p2_pd: s.pd, p2_zone: s.zone, p2_packet_status: "PROVISIONAL" };
        });
      },
      async decide(id, approve, note) {
        if (live) return void (await api.decide(id, { approve, note: note || null, ...OFFICER }), await refresh());
        if (approve && boardRef.current?.veto.track1_frozen) {
          throw new ApiError(409, "Track 1 veto is frozen: Pillar 2 withholds the packet, so no facility can be opened.");
        }
        patch(id, () =>
          approve
            ? { status: "approved", approved_at: now(), originated_at: now(), approved_by: OFFICER.officer_name, approval_note: note || null, facility_id: `fac-${id}` }
            : { status: "rejected", approved_by: OFFICER.officer_name, approval_note: note || null },
        );
      },
      async disburse(id) {
        if (live) return void (await api.disburse(id, null), await refresh());
        if (boardRef.current?.veto.track1_frozen) {
          throw new ApiError(409, "Track 1 veto is frozen: Pillar 4 blocks new disbursements until governance lifts it.");
        }
        patch(id, () => ({ status: "disbursed", disbursed_at: now() }));
      },
      async create(body) {
        if (live) {
          const { candidate } = await api.createCandidate(body);
          await refresh();
          return candidate;
        }
        const candidate = fixtureCandidate(body);
        const b = boardRef.current!;
        apply({ ...b, candidates: [candidate, ...b.candidates] });
        return candidate;
      },
      async advanceMonth() {
        if (live) return void (await api.tick(), await refresh());
        const b = boardRef.current!;
        apply({ ...b, month: b.month + 1 });
      },
      async reset() {
        if (live) return void (await api.reset(), await refresh());
        apply({ ...fixtureBoard(), month: 0 });
      },
    };
  }, [board, source, moved, refresh, patch, apply]);

  return <BoardContext.Provider value={value}>{children}</BoardContext.Provider>;
}

export function useBoard() {
  const ctx = useContext(BoardContext);
  if (!ctx) throw new Error("useBoard must be used inside <BoardProvider>");
  return ctx;
}
