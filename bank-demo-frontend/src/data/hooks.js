import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { API } from "./api";

// One invalidation key list shared by the SSE provider (src/components/shared/SseProvider.jsx)
// and every screen. Any live event (tick / state_update / reset) touches P1
// state directly and P3/P4 indirectly, so we refetch all of it together —
// the API doc is explicit that SSE only carries the P1 snapshot, nothing
// from P3/P4 is pushed, so the frontend has to go re-pull those itself.
export const LIVE_KEYS = [
  ["demoState"],
  ["facilities"],
  ["p4Capital"],
  ["p4Adequacy"],
  ["p4Ifrs9"],
  ["p4Balances"],
  ["ready"],
  ["bilan"],
];

export function invalidateLive(queryClient) {
  LIVE_KEYS.forEach((key) => queryClient.invalidateQueries({ queryKey: key }));
}

/** Deterministic post-action refresh: awaited, first cancelling any in-flight
 *  stale fetch so its response can never overwrite the fresh one. This is what
 *  makes pipeline actions apply on click instead of only after a page reload. */
async function refreshLive(queryClient) {
  await Promise.all(
    LIVE_KEYS.map((key) =>
      queryClient.refetchQueries({ queryKey: key, cancelRefetch: true })
    )
  );
}

export function useDemoStatePoll(pollMs = 6000) {
  return useQuery({
    queryKey: ["demoState"],
    queryFn: ({ signal }) => API.demoState(signal),
    refetchInterval: pollMs,
  });
}

export function useReady() {
  return useQuery({ queryKey: ["ready"], queryFn: API.ready, refetchInterval: 15000 });
}

export function useFacilities() {
  return useQuery({
    queryKey: ["facilities"],
    queryFn: ({ signal }) => API.facilities(signal),
  });
}

export function useFacility(id) {
  return useQuery({ queryKey: ["facility", id], queryFn: () => API.facility(id), enabled: !!id });
}

export function useFacilityAudit(id) {
  return useQuery({ queryKey: ["facilityAudit", id], queryFn: () => API.facilityAudit(id), enabled: !!id });
}

export function useCandidate(id) {
  return useQuery({ queryKey: ["candidate", id], queryFn: () => API.candidate(id), enabled: !!id });
}

export function useP4Capital() {
  return useQuery({ queryKey: ["p4Capital"], queryFn: API.p4Capital });
}

export function useP4Adequacy() {
  return useQuery({ queryKey: ["p4Adequacy"], queryFn: API.p4Adequacy });
}

export function useP4Ifrs9() {
  return useQuery({ queryKey: ["p4Ifrs9"], queryFn: API.p4Ifrs9 });
}

/** Live balance sheet. SSE frames invalidate it like every other live key, so
 *  anything done through the UI repaints instantly — but the background
 *  auto-tick and a direct P3 API write publish no SSE at all, hence the 5s
 *  safety poll. Only mounted on /bilan, so the other screens pay nothing. */
export function useBilan() {
  return useQuery({
    queryKey: ["bilan"],
    queryFn: ({ signal }) => API.bilan(signal),
    refetchInterval: 5000,
  });
}

export function useMode() {
  return useQuery({ queryKey: ["mode"], queryFn: API.p4Mode });
}

export function useVetoNotifications() {
  return useQuery({ queryKey: ["vetoNotifications"], queryFn: API.p4VetoNotifications, refetchInterval: 15000 });
}

export function useVetoLog() {
  return useQuery({ queryKey: ["vetoLog"], queryFn: API.vetoLog, refetchInterval: 15000 });
}

export function useCanon() {
  return useQuery({ queryKey: ["canon"], queryFn: API.canonCurrent });
}

export function useDemoProfiles() {
  return useQuery({ queryKey: ["demoProfiles"], queryFn: API.demoProfiles });
}

// ---- Mutations (refresh the live key set on settle — success AND error —
// so a vetoed/blocked action still repaints the board instead of leaving the
// UI stale until a manual reload) ----

function useLiveMutation(fn) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSettled: () => refreshLive(qc),
  });
}

export function useTick() {
  return useLiveMutation(API.demoTick);
}

export function useReset() {
  return useLiveMutation(API.demoReset);
}

export function useSeedDemo() {
  return useLiveMutation(API.demoSeed);
}

export function useCreateCandidate() {
  return useLiveMutation(API.createCandidate);
}

export function useImportCandidate() {
  return useLiveMutation(API.importCandidate);
}

export function useSubmitCandidate() {
  return useLiveMutation(API.submitCandidate);
}

export function useApproveCandidate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, decision }) => API.approveCandidate(id, decision),
    onSettled: () => refreshLive(qc),
  });
}

export function useDisburseCandidate() {
  return useLiveMutation(API.disburseCandidate);
}

export function useLiftTrack1() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (governanceRef) => API.p4LiftTrack1(governanceRef),
    onSettled: () => refreshLive(qc),
  });
}
