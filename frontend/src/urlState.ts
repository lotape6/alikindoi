// Keeps the current view, filters and open job in the URL, so the browser's
// back/forward buttons work and any view can be bookmarked or shared.
import { useCallback, useEffect, useState } from 'react'
import type { JobFilters } from './api'

export type View =
  | 'inbox' | 'all' | 'starred' | 'follow_up' | 'pipeline' | 'saved' | 'applied'
  | 'interviewing' | 'offer' | 'archived' | 'closed' | 'activity' | 'sources' | 'settings'

export interface UrlState {
  view: View
  filters: JobFilters
  job: number | null
}

const ARRAY_KEYS = ['tags', 'source', 'seniority', 'remote_type'] as const
const NUMBER_KEYS = ['salary_min', 'fit_min', 'page'] as const
const BOOL_KEYS = ['has_salary'] as const
const STRING_KEYS = ['q', 'city', 'sort_by', 'sort_dir'] as const

export function readUrl(): UrlState {
  const p = new URLSearchParams(window.location.search)
  const filters: JobFilters = {}
  for (const key of ARRAY_KEYS) {
    const values = p.getAll(key)
    if (values.length) filters[key] = values
  }
  for (const key of NUMBER_KEYS) {
    const v = p.get(key)
    if (v && !Number.isNaN(Number(v))) filters[key] = Number(v)
  }
  for (const key of BOOL_KEYS) if (p.get(key) === '1') filters[key] = true
  for (const key of STRING_KEYS) {
    const v = p.get(key)
    if (v) (filters as Record<string, string>)[key] = v
  }
  const job = Number(p.get('job'))
  return { view: (p.get('view') as View) || 'inbox', filters, job: job || null }
}

function writeUrl(state: UrlState, push: boolean) {
  const p = new URLSearchParams()
  if (state.view !== 'inbox') p.set('view', state.view)
  for (const [key, value] of Object.entries(state.filters)) {
    if (value === undefined || value === '' || value === false) continue
    if (key === 'page' && value === 1) continue
    if (Array.isArray(value)) value.forEach((v) => p.append(key, String(v)))
    else p.set(key, value === true ? '1' : String(value))
  }
  if (state.job) p.set('job', String(state.job))
  const url = `${window.location.pathname}${p.toString() ? `?${p}` : ''}`
  if (url === `${window.location.pathname}${window.location.search}`) return
  if (push) window.history.pushState(null, '', url)
  else window.history.replaceState(null, '', url)
}

export function useUrlState(): [UrlState, (patch: Partial<UrlState>, push?: boolean) => void] {
  const [state, setState] = useState<UrlState>(readUrl)

  useEffect(() => {
    const onPop = () => setState(readUrl())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const update = useCallback((patch: Partial<UrlState>, push = false) => {
    setState((prev) => {
      const next = { ...prev, ...patch }
      writeUrl(next, push)
      return next
    })
  }, [])

  return [state, update]
}
