import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import { fetchJob, patchJob, type JobDetail as Detail, type JobPatch } from '../api'
import {
  CLOSED_REASON, STATUS_LABEL, STATUS_STYLE, fitStyle, isDue, locationText, relativeDate,
  salaryEur, salaryOriginal, shortList, sourceLabel, workplace,
} from '../format'

const PIPELINE = ['new', 'saved', 'applied', 'interviewing', 'offer'] as const
const SENIORITY = ['junior', 'mid', 'senior', 'lead']
const REMOTE_TYPES = ['remote', 'hybrid', 'onsite', 'unknown']
const INTERVALS = ['yearly', 'monthly', 'weekly', 'daily', 'hourly']

const EVENT_LABELS: Record<string, string> = {
  discovered: 'Found',
  reconfirmed: 'Still listed',
  salary_changed: 'Salary changed',
  description_changed: 'Description updated',
  removed: 'Position closed',
  reappeared: 'Listed again',
  applied: 'Applied',
  status_changed: 'Status changed',
  dedup_alias: 'Merged into another record',
  listing_added: 'Also listed on another board',
  listing_closed: 'A board stopped listing it',
  follow_up_set: 'Follow-up set',
  closed: 'Closed by you',
  reopened: 'Reopened',
  enriched: 'Data enriched',
  edited: 'Edited',
}

const input = 'rounded-md bg-slate-900 px-2 py-1.5 text-sm ring-1 ring-slate-700 focus:outline-none focus:ring-indigo-500'

function eventDetail(e: Detail['events'][number]): string {
  const p = (e.payload ?? {}) as Record<string, unknown>
  switch (e.event_type) {
    case 'status_changed':
    case 'applied':
      return `${STATUS_LABEL[String(p.from)] ?? p.from} → ${STATUS_LABEL[String(p.to)] ?? p.to}`
    case 'listing_added':
    case 'listing_closed':
      return [sourceLabel(String(p.source)), p.reason ? CLOSED_REASON[String(p.reason)] ?? p.reason : '']
        .filter(Boolean).join(' · ')
    case 'removed':
      return CLOSED_REASON[String(p.reason)] ?? ''
    case 'follow_up_set':
      return [p.action, p.due].filter(Boolean).join(' · ') || 'cleared'
    case 'edited':
      return `${p.field}: ${JSON.stringify(p.from)} → ${JSON.stringify(p.to)}`
    case 'salary_changed':
      return `${JSON.stringify(p.from)} → ${JSON.stringify(p.to)}`
    case 'reappeared':
      return p.source ? sourceLabel(String(p.source)) : ''
    default:
      return ''
  }
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-200">{children}</dd>
    </div>
  )
}

function Section({ title, children, aside }: { title: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">{title}</h3>
        {aside}
      </div>
      {children}
    </section>
  )
}

interface Props {
  jobId: number
  onClose: () => void
  onPrev?: () => void
  onNext?: () => void
  position?: string
}

export default function JobDetail({ jobId, onClose, onPrev, onNext, position }: Props) {
  const queryClient = useQueryClient()
  const { data: job, isLoading, isError } = useQuery({ queryKey: ['job', jobId], queryFn: () => fetchJob(jobId) })
  const [draft, setDraft] = useState<{ notes?: string; action?: string; due?: string; contact?: string }>({})
  const [tagInput, setTagInput] = useState('')
  const [editing, setEditing] = useState(false)

  useEffect(() => {
    setDraft({})
    setEditing(false)
  }, [jobId])

  const mutation = useMutation({
    mutationFn: (patch: JobPatch) => patchJob(jobId, patch),
    onSuccess: (updated) => {
      queryClient.setQueryData(['job', jobId], updated)
      for (const key of ['jobs', 'stats', 'events', 'views', 'pipeline']) {
        queryClient.invalidateQueries({ queryKey: [key] })
      }
    },
  })
  const save = (patch: JobPatch) => mutation.mutate(patch)

  const numOrUndef = (v: string) => (v === '' ? undefined : Number(v))

  return (
    <aside className="fixed inset-y-0 right-0 z-40 flex w-full max-w-2xl flex-col border-l border-slate-800 bg-slate-950 shadow-2xl">
      <header className="flex items-center gap-2 border-b border-slate-800 px-5 py-3 text-sm">
        <button onClick={onPrev} disabled={!onPrev} className="rounded px-2 py-1 text-slate-300 hover:bg-slate-800 disabled:opacity-30" title="Previous (k)">
          ↑
        </button>
        <button onClick={onNext} disabled={!onNext} className="rounded px-2 py-1 text-slate-300 hover:bg-slate-800 disabled:opacity-30" title="Next (j)">
          ↓
        </button>
        {position && <span className="text-xs text-slate-500">{position}</span>}
        <span className="ml-auto text-xs text-slate-600">j / k to move · Esc to close</span>
        <button onClick={onClose} className="rounded px-2 py-1 text-slate-400 hover:bg-slate-800 hover:text-white" title="Close (Esc)">
          ✕
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        {isError && <p className="text-red-400">Could not load this position.</p>}
        {(isLoading || !job) && !isError && <p className="text-slate-400">Loading…</p>}
        {job && (
          <div className="space-y-7">
            {/* Title block */}
            <div className="space-y-3">
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <h2 className="text-xl font-semibold leading-snug">{job.title}</h2>
                  <p className="mt-1 text-slate-400">
                    {job.company} · {workplace(job)} · {locationText(job)}
                  </p>
                </div>
                <button
                  onClick={() => save({ starred: !job.starred })}
                  className={`text-xl ${job.starred ? 'text-amber-400' : 'text-slate-600 hover:text-slate-400'}`}
                  title={job.starred ? 'Unstar' : 'Star'}
                >
                  {job.starred ? '★' : '☆'}
                </button>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded px-2 py-0.5 text-xs font-semibold ${fitStyle(job.fit_score)}`}>
                  Fit {job.fit_score != null ? Math.round(job.fit_score) : '–'}
                </span>
                {job.fit_notes?.map((n) => (
                  <span key={n} className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400">{n}</span>
                ))}
                {!job.is_active && (
                  <span className="rounded bg-zinc-800 px-2 py-0.5 text-xs text-zinc-300">
                    Closed {relativeDate(job.closed_at)} · {CLOSED_REASON[job.closed_reason ?? ''] ?? job.closed_reason}
                  </span>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                <a href={job.url} target="_blank" rel="noreferrer" className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium hover:bg-indigo-500">
                  Open posting ↗
                </a>
                {job.app_status === 'new' && job.is_active && (
                  <button onClick={() => save({ app_status: 'saved' })} className="rounded-md bg-slate-800 px-3 py-1.5 text-sm hover:bg-slate-700">
                    Shortlist
                  </button>
                )}
                {job.app_status !== 'applied' && job.is_active && (
                  <button onClick={() => save({ app_status: 'applied' })} className="rounded-md bg-slate-800 px-3 py-1.5 text-sm hover:bg-slate-700">
                    Mark applied
                  </button>
                )}
                {job.app_status === 'new' && (
                  <button onClick={() => save({ app_status: 'withdrawn' })} className="rounded-md px-3 py-1.5 text-sm text-slate-400 hover:bg-slate-800">
                    Not interested
                  </button>
                )}
                <button
                  onClick={() => save({ is_open: !job.is_active })}
                  className="ml-auto rounded-md px-3 py-1.5 text-sm text-slate-400 hover:bg-slate-800"
                >
                  {job.is_active ? 'Mark closed' : 'Reopen'}
                </button>
              </div>
            </div>

            {/* Pipeline stepper */}
            <Section title="Application">
              <div className="flex overflow-hidden rounded-md ring-1 ring-slate-800">
                {PIPELINE.map((s) => {
                  const reached = PIPELINE.indexOf(job.app_status as (typeof PIPELINE)[number]) >= PIPELINE.indexOf(s)
                  const current = job.app_status === s
                  return (
                    <button
                      key={s}
                      onClick={() => save({ app_status: s })}
                      className={`flex-1 px-2 py-2 text-xs ${
                        current ? 'bg-indigo-600 text-white' : reached ? 'bg-indigo-500/15 text-indigo-200' : 'bg-slate-900 text-slate-400 hover:bg-slate-800'
                      }`}
                    >
                      {STATUS_LABEL[s]}
                    </button>
                  )
                })}
              </div>
              <div className="flex gap-2 text-xs">
                {(['rejected', 'withdrawn'] as const).map((s) => (
                  <button
                    key={s}
                    onClick={() => save({ app_status: s })}
                    className={`rounded-full px-2.5 py-1 ring-1 ${job.app_status === s ? STATUS_STYLE[s] : 'text-slate-500 ring-slate-800 hover:text-slate-300'}`}
                  >
                    {STATUS_LABEL[s]}
                  </button>
                ))}
                {job.applied_at && <span className="ml-auto self-center text-slate-500">Applied {relativeDate(job.applied_at)}</span>}
              </div>
            </Section>

            {/* Tracking */}
            <Section title="Next step & notes">
              <div className="grid grid-cols-[1fr_auto] gap-2">
                <input
                  className={input}
                  placeholder="Next action, e.g. Follow up with the recruiter"
                  value={draft.action ?? job.next_action ?? ''}
                  onChange={(e) => setDraft((d) => ({ ...d, action: e.target.value }))}
                  onBlur={() => draft.action !== undefined && draft.action !== (job.next_action ?? '') && save({ next_action: draft.action })}
                />
                <input
                  type="date"
                  className={`${input} ${isDue(job.next_action_at) ? 'text-red-300 ring-red-500/50' : ''}`}
                  value={draft.due ?? job.next_action_at ?? ''}
                  onChange={(e) => {
                    setDraft((d) => ({ ...d, due: e.target.value }))
                    save({ next_action_at: e.target.value })
                  }}
                />
              </div>
              <input
                className={`${input} w-full`}
                placeholder="Contact (recruiter, hiring manager, email…)"
                value={draft.contact ?? job.contact ?? ''}
                onChange={(e) => setDraft((d) => ({ ...d, contact: e.target.value }))}
                onBlur={() => draft.contact !== undefined && draft.contact !== (job.contact ?? '') && save({ contact: draft.contact })}
              />
              <textarea
                className={`${input} h-28 w-full`}
                placeholder="Notes: interview feedback, questions, salary talks…"
                value={draft.notes ?? job.app_notes ?? ''}
                onChange={(e) => setDraft((d) => ({ ...d, notes: e.target.value }))}
                onBlur={() => draft.notes !== undefined && draft.notes !== (job.app_notes ?? '') && save({ app_notes: draft.notes })}
              />
            </Section>

            {/* Key facts */}
            <Section
              title="Details"
              aside={
                <button onClick={() => setEditing((e) => !e)} className="text-xs text-slate-400 hover:text-slate-200">
                  {editing ? 'Done' : 'Correct details'}
                </button>
              }
            >
              <dl className="grid grid-cols-2 gap-x-6 gap-y-3 rounded-lg bg-slate-900/50 p-4 ring-1 ring-slate-800 sm:grid-cols-3">
                <Fact label="Salary (EUR / year)">{salaryEur(job) ?? 'Not stated'}</Fact>
                <Fact label="As published">{salaryOriginal(job) ?? '—'}</Fact>
                <Fact label="Seniority">{job.seniority ?? '—'}</Fact>
                <Fact label="Workplace">{workplace(job)}</Fact>
                <Fact label="Location">
                  <span title={job.region ?? undefined}>{job.city ?? (job.region ? shortList(job.region, 6) : '—')}</span>
                </Fact>
                <Fact label="Contract">{job.job_type ?? '—'}</Fact>
                <Fact label="Posted">{job.date_posted ?? '—'}</Fact>
                <Fact label="First found">{relativeDate(job.first_seen_at)}</Fact>
                <Fact label="Last seen on a board">{relativeDate(job.last_seen_at)}</Fact>
                {job.expires_at && <Fact label="Expires">{job.expires_at}</Fact>}
              </dl>
              {editing && (
                <div className="space-y-2 rounded-lg p-4 ring-1 ring-slate-800">
                  <div className="flex flex-wrap items-center gap-2">
                    <select className={input} value={job.seniority ?? ''} onChange={(e) => save({ seniority: e.target.value || undefined })}>
                      <option value="">Seniority</option>
                      {SENIORITY.map((s) => <option key={s}>{s}</option>)}
                    </select>
                    <select className={input} value={job.remote_type ?? ''} onChange={(e) => save({ remote_type: e.target.value || undefined })}>
                      <option value="">Workplace</option>
                      {REMOTE_TYPES.map((s) => <option key={s}>{s}</option>)}
                    </select>
                    <input
                      className={`${input} w-36`}
                      placeholder="City"
                      defaultValue={job.city ?? ''}
                      onBlur={(e) => e.target.value !== (job.city ?? '') && save({ city: e.target.value || undefined })}
                    />
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <input type="number" className={`${input} w-28`} placeholder="min" defaultValue={job.salary_min ?? ''}
                      onBlur={(e) => numOrUndef(e.target.value) !== job.salary_min && save({ salary_min: numOrUndef(e.target.value) })} />
                    <span className="text-slate-500">–</span>
                    <input type="number" className={`${input} w-28`} placeholder="max" defaultValue={job.salary_max ?? ''}
                      onBlur={(e) => numOrUndef(e.target.value) !== job.salary_max && save({ salary_max: numOrUndef(e.target.value) })} />
                    <input className={`${input} w-20`} placeholder="EUR" defaultValue={job.salary_currency ?? ''}
                      onBlur={(e) => e.target.value !== (job.salary_currency ?? '') && save({ salary_currency: e.target.value.toUpperCase() || undefined })} />
                    <select className={input} value={job.salary_interval ?? 'yearly'} onChange={(e) => save({ salary_interval: e.target.value })}>
                      {INTERVALS.map((s) => <option key={s}>{s}</option>)}
                    </select>
                  </div>
                </div>
              )}
              <div className="flex flex-wrap items-center gap-1.5">
                {job.tags.map((t) => (
                  <span key={t} className="flex items-center gap-1 rounded-full bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
                    {t}
                    {editing && (
                      <button className="text-slate-500 hover:text-red-400" onClick={() => save({ tags: job.tags.filter((x) => x !== t) })}>
                        ✕
                      </button>
                    )}
                  </span>
                ))}
                {editing && (
                  <input
                    className={`${input} w-28 py-0.5 text-xs`}
                    placeholder="+ skill"
                    value={tagInput}
                    onChange={(e) => setTagInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && tagInput.trim()) {
                        save({ tags: [...job.tags, tagInput.trim().toLowerCase()] })
                        setTagInput('')
                      }
                    }}
                  />
                )}
              </div>
            </Section>

            {/* Listings across boards */}
            <Section title={`Listed on ${job.listings.length} board${job.listings.length === 1 ? '' : 's'}`}>
              <ul className="divide-y divide-slate-800 rounded-lg ring-1 ring-slate-800">
                {job.listings.map((l) => (
                  <li key={l.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                    <span className={`h-2 w-2 rounded-full ${l.is_open ? 'bg-emerald-400' : 'bg-zinc-600'}`} />
                    <a href={l.url} target="_blank" rel="noreferrer" className="font-medium text-slate-200 hover:text-indigo-300">
                      {sourceLabel(l.source)} ↗
                    </a>
                    <span className="text-xs text-slate-500">
                      {l.is_open ? `seen ${relativeDate(l.last_seen_at)}` : `gone ${relativeDate(l.closed_at)}`}
                    </span>
                    {l.salary_max && (
                      <span className="ml-auto text-xs text-slate-400">
                        {salaryOriginal({ salary_min: l.salary_min, salary_max: l.salary_max, salary_currency: l.salary_currency, salary_interval: null })}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </Section>

            {job.description && (
              <Section title="Description">
                <div className="description rounded-lg bg-slate-900/40 p-4 text-sm text-slate-300 ring-1 ring-slate-800">
                  <ReactMarkdown>{job.description}</ReactMarkdown>
                </div>
              </Section>
            )}

            <Section title="Timeline">
              <ol className="relative space-y-3 border-l border-slate-800 pl-4">
                {[...job.events]
                  .reverse()
                  .filter((e) => e.event_type !== 'reconfirmed')
                  .map((e) => (
                    <li key={e.id} className="text-sm">
                      <span className="absolute -left-1 mt-1.5 h-2 w-2 rounded-full bg-slate-700" />
                      <p className="text-slate-200">
                        {EVENT_LABELS[e.event_type] ?? e.event_type}
                        <span className="text-slate-500"> {eventDetail(e)}</span>
                      </p>
                      <p className="text-xs text-slate-500">{new Date(e.created_at).toLocaleString()}</p>
                    </li>
                  ))}
              </ol>
            </Section>
          </div>
        )}
      </div>
    </aside>
  )
}
