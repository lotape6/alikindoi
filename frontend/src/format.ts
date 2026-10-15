// Display helpers shared by the list, board and detail views.
import type { Job } from './api'

export const STATUSES = ['new', 'saved', 'applied', 'interviewing', 'offer', 'rejected', 'withdrawn'] as const

export const STATUS_LABEL: Record<string, string> = {
  new: 'New',
  saved: 'Shortlisted',
  applied: 'Applied',
  interviewing: 'Interviewing',
  offer: 'Offer',
  rejected: 'Rejected',
  withdrawn: 'Withdrawn',
}

export const STATUS_STYLE: Record<string, string> = {
  new: 'bg-sky-500/15 text-sky-300 ring-sky-500/30',
  saved: 'bg-slate-500/20 text-slate-200 ring-slate-400/30',
  applied: 'bg-indigo-500/15 text-indigo-300 ring-indigo-500/30',
  interviewing: 'bg-amber-500/15 text-amber-300 ring-amber-500/30',
  offer: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/30',
  rejected: 'bg-red-500/10 text-red-300 ring-red-500/25',
  withdrawn: 'bg-zinc-500/15 text-zinc-400 ring-zinc-500/25',
}

export const CLOSED_REASON: Record<string, string> = {
  removed_from_board: 'Removed from the board',
  posting_gone: 'Posting page is gone',
  expired: 'Past its expiry date',
  stale: 'Not listed for 30 days',
  manual: 'Closed by you',
}

export const SOURCE_LABEL: Record<string, string> = {
  linkedin: 'LinkedIn',
  indeed: 'Indeed',
  glassdoor: 'Glassdoor',
  google: 'Google Jobs',
  zip_recruiter: 'ZipRecruiter',
  adzuna: 'Adzuna',
  remotive: 'Remotive',
  themuse: 'The Muse',
  himalayas: 'Himalayas',
  remoteok: 'Remote OK',
  jobicy: 'Jobicy',
  arbeitnow: 'Arbeitnow',
  weworkremotely: 'We Work Remotely',
}

export const sourceLabel = (s: string) => SOURCE_LABEL[s] ?? s

const k = (n: number) => `${Math.round(n / 1000)}k`

/** "60k–80k €" from the EUR-normalized annual range. */
export function salaryEur(job: Pick<Job, 'salary_annual_min' | 'salary_annual_max'>): string | null {
  const lo = job.salary_annual_min
  const hi = job.salary_annual_max
  if (!lo && !hi) return null
  if (lo && hi && Math.round(lo / 1000) !== Math.round(hi / 1000)) return `${k(lo)}–${k(hi)} €`
  return `${k((hi ?? lo)!)} €`
}

/** The salary as the board published it, e.g. "120,000–150,000 USD / yearly". */
export function salaryOriginal(job: Pick<Job, 'salary_min' | 'salary_max' | 'salary_currency' | 'salary_interval'>): string | null {
  const { salary_min: lo, salary_max: hi } = job
  if (!lo && !hi) return null
  const fmt = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 0 })
  const range = lo && hi && lo !== hi ? `${fmt(lo)}–${fmt(hi)}` : fmt((hi ?? lo)!)
  return `${range} ${job.salary_currency ?? ''}${job.salary_interval && job.salary_interval !== 'yearly' ? ` / ${job.salary_interval}` : ''}`.trim()
}

export function workplace(job: Pick<Job, 'remote_type' | 'is_remote'>): string {
  const t = job.remote_type ?? (job.is_remote ? 'remote' : null)
  return t === 'remote' ? 'Remote' : t === 'hybrid' ? 'Hybrid' : t === 'onsite' ? 'On-site' : 'Unspecified'
}

export function locationText(job: Pick<Job, 'city' | 'region' | 'country' | 'remote_type' | 'is_remote'>): string {
  if (job.city) return [job.city, job.country].filter(Boolean).join(', ')
  if (job.region) return shortList(job.region, 3)
  return job.country ?? '—'
}

/** "Spain, Portugal, France +4 more" from a comma-separated list. */
export function shortList(text: string, max: number): string {
  const parts = text.split(',').map((p) => p.trim()).filter(Boolean)
  return parts.length > max ? `${parts.slice(0, max).join(', ')} +${parts.length - max} more` : parts.join(', ')
}

export function relativeDate(value: string | null | undefined): string {
  if (!value) return '—'
  const then = new Date(value.length === 10 ? `${value}T00:00:00` : value).getTime()
  const days = Math.floor((Date.now() - then) / 86_400_000)
  if (days < 0) return days === -1 ? 'tomorrow' : `in ${-days} days`
  if (days === 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 30) return `${days}d ago`
  if (days < 365) return `${Math.floor(days / 30)}mo ago`
  return `${Math.floor(days / 365)}y ago`
}

export function isDue(date: string | null | undefined): boolean {
  if (!date) return false
  return date <= new Date().toISOString().slice(0, 10)
}

export function fitStyle(score: number | null | undefined): string {
  if (score == null) return 'bg-slate-800 text-slate-400'
  if (score >= 75) return 'bg-emerald-500/20 text-emerald-300'
  if (score >= 55) return 'bg-lime-500/15 text-lime-300'
  if (score >= 40) return 'bg-amber-500/15 text-amber-300'
  return 'bg-slate-800 text-slate-400'
}
