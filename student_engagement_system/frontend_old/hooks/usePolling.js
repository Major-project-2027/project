/**
 * Phase 8 Dashboard -- "hooks" (vanilla-JS equivalents: no React runtime
 * is used anywhere in this dashboard, so these are plain reusable
 * functions that mimic the same call pattern for readability).
 */

/**
 * Repeatedly call `fn` every `intervalMs`, immediately and then on a
 * timer. Returns a `stop()` function. Used by Dashboard Home for the
 * "live" stat cards and by Analytics for auto-refreshing charts.
 */
export function usePolling(fn, intervalMs = 5000) {
  let stopped = false;
  const tick = async () => {
    if (stopped) return;
    try {
      await fn();
    } catch (err) {
      console.error("usePolling tick failed:", err); // eslint-disable-line no-console
    }
  };
  tick();
  const handle = setInterval(tick, intervalMs);
  return function stop() {
    stopped = true;
    clearInterval(handle);
  };
}

/**
 * Minimal pub-sub store, used for cross-component state such as the
 * active theme so the navbar toggle and every chart can react without a
 * framework.
 */
export function createStore(initialValue) {
  let value = initialValue;
  const listeners = new Set();
  return {
    get: () => value,
    set(next) {
      value = typeof next === "function" ? next(value) : next;
      listeners.forEach((listener) => listener(value));
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
