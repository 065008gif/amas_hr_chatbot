// Backend client. The address comes from VITE_API_URL (set in Vercel for the deployed site).
export const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(kind, message, status) {
    super(message)
    this.kind = kind // offline | warming | rate_limit | not_signed_in | not_found | server
    this.status = status
  }
}

let employeeId = null
export const setEmployee = (id) => { employeeId = id }

export async function api(path, { method = 'GET', body, timeout = 90000 } = {}) {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    throw new ApiError('offline', 'You appear to be offline. Check your connection and try again.')
  }
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeout)
  let res
  try {
    res = await fetch(API_URL + path, {
      method,
      headers: { 'Content-Type': 'application/json', ...(employeeId ? { 'X-Employee-Id': employeeId } : {}) },
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    })
  } catch (e) {
    throw new ApiError(e.name === 'AbortError' ? 'server' : 'warming',
      e.name === 'AbortError' ? 'The request took too long. Please try again.'
        : 'The HR assistant server is not reachable yet. It may be waking up.')
  } finally {
    clearTimeout(timer)
  }
  let data = null
  try { data = await res.json() } catch { /* non-JSON */ }
  if (res.ok) return data
  if (res.status === 503) throw new ApiError('warming', data?.detail || 'Nia is warming up, please try again in a few seconds.', 503)
  if (res.status === 429) throw new ApiError('rate_limit', data?.answer || 'The free model limit was reached, please try again shortly.', 429)
  if (res.status === 401) throw new ApiError('not_signed_in', data?.detail || 'Please choose a demo employee.', 401)
  if (res.status === 404) throw new ApiError('not_found', data?.detail || 'Not found.', 404)
  throw new ApiError('server', data?.detail || `Something went wrong (HTTP ${res.status}).`, res.status)
}

export const pdfUrl = (docId) => `${API_URL}/pdf/${docId}`
