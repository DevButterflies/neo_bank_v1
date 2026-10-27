import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";
import type { BoardSnapshot } from "../api/types";
import { useBoard } from "./board";

interface AreaState<T> {
  data: T | null;
  error: ApiError | null;
  /** replace the data, used by offline actions */
  setData(update: (d: T) => T): void;
  reload(): void;
  live: boolean;
}

/**
 * Loads an area's data from the API, or from its demo fixture when the board runs on demo data.
 * The source is decided once by the board, so every screen agrees on live vs demo.
 */
export function useArea<T>(load: () => Promise<T>, demo: (board: BoardSnapshot) => T): AreaState<T> {
  const { board, source } = useBoard();
  const [data, setDataState] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [nonce, setNonce] = useState(0);
  const loadRef = useRef(load);
  const demoRef = useRef(demo);
  loadRef.current = load;
  demoRef.current = demo;
  const boardRef = useRef(board);
  boardRef.current = board;
  // demo data is seeded from the board once; refresh it when the bank is reset or the veto scenario changes
  const demoKey = source === "demo" && board ? `${board.veto.track1_frozen}-${board.candidates.length}-${board.month === 0}` : "";

  useEffect(() => {
    if (source === "connecting" || !boardRef.current) return;
    if (source === "demo") {
      setDataState(demoRef.current(boardRef.current));
      return;
    }
    let cancelled = false;
    setError(null);
    loadRef
      .current()
      .then((d) => !cancelled && setDataState(d))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e : new ApiError(0, "The API could not be reached.")));
    return () => {
      cancelled = true;
    };
  }, [source, nonce, demoKey]);

  const setData = useCallback((update: (d: T) => T) => setDataState((d) => (d == null ? d : update(d))), []);
  const reload = useCallback(() => setNonce((n) => n + 1), []);

  return { data, error, setData, reload, live: source === "live" };
}
