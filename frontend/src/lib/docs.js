import { api } from './api.js'

let cache = null
export function getDocs() {
  if (!cache) cache = api('/docs-list').then((d) => d.documents).catch((e) => { cache = null; throw e })
  return cache
}
