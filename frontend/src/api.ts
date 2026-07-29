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
