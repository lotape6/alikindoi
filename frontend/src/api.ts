// API client + shared types

export interface Job {
  id: number
  source: string
  title: string
  company: string
  url: string
  city: string | null
  region: string | null
  country: string | null
  is_remote: boolean | null
  remote_type: string | null
  job_type: string | null
  seniority: string | null
  salary_min: number | null
  salary_max: number | null
  salary_currency: string | null
  salary_annual_min: number | null
  salary_annual_max: number | null
  date_posted: string | null
  first_seen_at: string
  last_seen_at: string
  is_active: boolean
  app_status: string
  profile_name: string | null
  tags: string[]
}

export interface JobEvent {
  id: number
  event_type: string
  payload: Record<string, unknown> | null
  created_at: string
}

export interface JobDetail extends Job {
  description: string | null
  app_notes: string | null
  applied_at: string | null
  events: JobEvent[]
}

export interface JobFilters {
  q?: string
  tags?: string[]
  source?: string[]
  seniority?: string[]
  remote_type?: string[]
  city?: string
  app_status?: string[]
  salary_min?: number
  salary_max?: number
  removed?: boolean
  new_only?: boolean
  has_salary?: boolean
  sort_by?: string
  sort_dir?: 'asc' | 'desc'
  page?: number
  page_size?: number
}

export interface Stats {
  total: number
  active: number
  removed: number
  new: number
  by_source: Record<string, number>
  by_status: Record<string, number>
  salary_avg_max: number | null
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const fetchJobs = (filters: JobFilters): Promise<{ total: number; items: Job[] }> => {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === '' || value === false) continue
    if (Array.isArray(value)) value.forEach((v) => params.append(key, String(v)))
    else params.set(key, String(value))
  }
  return get(`/api/jobs?${params}`)
}

export const fetchJob = (id: number): Promise<JobDetail> => get(`/api/jobs/${id}`)

export const fetchStats = (): Promise<Stats> => get('/api/stats')

export const fetchTags = (): Promise<Record<string, number>> => get('/api/tags')

export const fetchFilterOptions = (): Promise<{
  sources: string[]
  seniority: string[]
  remote_types: string[]
  cities: string[]
  app_statuses: string[]
}> => get('/api/filters')

export async function patchJob(
  id: number,
  patch: { app_status?: string; app_notes?: string },
): Promise<JobDetail> {
  const res = await fetch(`/api/jobs/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

// ---------- Admin ----------

export interface ScrapeRun {
  id: number
  started_at: string
  finished_at: string | null
  trigger: string
  profile_name: string
  source: string
  status: string
  jobs_found: number | null
  jobs_new: number | null
  jobs_removed: number | null
  error: string | null
}

export interface SearchProfile {
  name: string
  enabled: boolean
  search_term: string
  google_search_term: string | null
  location: string | null
  country_indeed: string
  adzuna_country: string
  is_remote: boolean | null
  job_type: string | null
  tags: string[]
  results_wanted: number
  hours_old: number | null
  interval_minutes: number
}

export interface RuntimeConfig {
  search_profiles: SearchProfile[]
  rate_limits: Record<string, unknown>
  sources: Record<string, Record<string, { enabled: boolean }>>
  notifications: Record<string, unknown>
}

export const fetchRuns = (): Promise<ScrapeRun[]> => get('/api/runs?limit=50')

export const fetchConfig = (): Promise<RuntimeConfig> => get('/api/config')

export const fetchScrapeStatus = (): Promise<{
  running: boolean
  started_at: string | null
  last_report: Record<string, string> | null
}> => get('/api/scrape/status')

export async function patchProfile(
  name: string,
  patch: Partial<SearchProfile>,
): Promise<SearchProfile> {
  const res = await fetch(`/api/config/profiles/${encodeURIComponent(name)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export async function triggerScrape(body: {
  profile?: string
  source?: string
  force?: boolean
}): Promise<{ status: string }> {
  const res = await fetch('/api/scrape', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export interface SourceInfo {
  name: string
  kind: 'scraper' | 'api'
  enabled: boolean
  available: boolean
  min_interval_minutes: number
  last_run: {
    at: string
    status: string
    jobs_found: number | null
    jobs_new: number | null
    error: string | null
  } | null
  running: boolean
}

export interface TimelinePoint {
  date: string
  discovered: number
  removed: number
  jobs_found: number
  jobs_new: number
  runs: number
}

export const fetchSources = (): Promise<SourceInfo[]> => get('/api/sources')

export const fetchTimeline = (): Promise<TimelinePoint[]> => get('/api/stats/timeline')

export async function createProfile(profile: Partial<SearchProfile>): Promise<SearchProfile> {
  const res = await fetch('/api/config/profiles', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile),
  })
  if (!res.ok) throw new Error((await res.json()).detail ?? `${res.status}`)
  return res.json()
}

export async function deleteProfile(name: string): Promise<void> {
  const res = await fetch(`/api/config/profiles/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
}

