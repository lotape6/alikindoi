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
  salary_interval: string | null
  salary_annual_min: number | null
  salary_annual_max: number | null
  date_posted: string | null
  first_seen_at: string
  last_seen_at: string
  is_active: boolean
  app_status: string
  profile_name: string | null
  tags: string[]
  fit_score: number | null
  fit_notes: string[] | null
  closed_at: string | null
  closed_reason: string | null
  expires_at: string | null
  next_action: string | null
  next_action_at: string | null
  starred: boolean
  sources: string[]
}

export interface Listing {
  id: number
  source: string
  url: string
  is_open: boolean
  first_seen_at: string
  last_seen_at: string
  closed_at: string | null
  salary_min: number | null
  salary_max: number | null
  salary_currency: string | null
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
  contact: string | null
  listings: Listing[]
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
  fit_min?: number
  starred?: boolean
  follow_up_due?: boolean
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

export interface JobPatch {
  app_status?: string
  app_notes?: string
  next_action?: string
  next_action_at?: string
  contact?: string
  starred?: boolean
  is_open?: boolean
  title?: string
  company?: string
  city?: string
  region?: string
  country?: string
  remote_type?: string
  job_type?: string
  seniority?: string
  salary_min?: number
  salary_max?: number
  salary_currency?: string
  salary_interval?: string
  tags?: string[]
}

export async function patchJob(id: number, patch: JobPatch): Promise<JobDetail> {
  const res = await fetch(`/api/jobs/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export interface ActivityEvent {
  id: number
  job_id: number
  job_title: string
  job_company: string
  event_type: string
  payload: Record<string, unknown> | null
  created_at: string
}

export const fetchEvents = (): Promise<ActivityEvent[]> => get('/api/events?limit=100')

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
  runs_per_day: number
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


// ---------- Views, closing and criteria ----------

export type ViewCounts = Record<
  'inbox' | 'all' | 'starred' | 'saved' | 'applied' | 'interviewing' | 'offer' | 'follow_up' | 'archived' | 'closed',
  number
>

export const fetchViews = (): Promise<ViewCounts> => get('/api/views')

export async function checkClosed(): Promise<{ closed: number }> {
  const res = await fetch('/api/jobs/check-closed', { method: 'POST' })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export interface Criteria {
  enabled: boolean
  min_salary_eur: number | null
  keep_unknown_salary: boolean
  seniority: string[]
  role_keywords: string[]
  exclude_title_keywords: string[]
  boost_keywords: string[]
  location: { remote_allowed_regions: string[]; hybrid_cities: string[] }
  fx_to_eur: Record<string, number>
}

export const fetchCriteria = (): Promise<Criteria> => get('/api/config/criteria')

export async function patchCriteria(patch: Partial<Criteria>): Promise<Criteria> {
  const res = await fetch('/api/config/criteria', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  if (!res.ok) throw new Error((await res.json()).detail ?? `${res.status}`)
  return res.json()
}
