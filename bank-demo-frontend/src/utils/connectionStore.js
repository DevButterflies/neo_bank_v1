// Minimal pub/sub (no extra dependency) so any component can show whether
// the last API calls actually reached the orchestrator, or the UI silently
// fell back to bundled mock data (see src/data/mock.js and README "Demo
// mode vs live mode").

let state = { live: null }; // null = unknown yet, true = live backend, false = mock fallback
const listeners = new Set();

export function reportConnection(isLive) {
  if (state.live === isLive) return;
  state = { live: isLive };
  listeners.forEach((fn) => fn(state));
}

export function getConnectionState() {
  return state;
}

export function subscribeConnection(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
