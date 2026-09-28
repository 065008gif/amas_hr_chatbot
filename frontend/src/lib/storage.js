// Small, safe wrappers around localStorage (it can be unavailable in private windows).
export function load(key, fallback) {
  try {
    const v = localStorage.getItem(key)
    return v == null ? fallback : JSON.parse(v)
  } catch { return fallback }
}
export function save(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* ignore */ }
}
export function remove(key) {
  try { localStorage.removeItem(key) } catch { /* ignore */ }
}
