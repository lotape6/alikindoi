import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import { fetchJob, patchJob, type JobPatch } from '../api'

const STATUSES = ['new', 'saved', 'applied', 'interviewing', 'offer', 'rejected', 'withdrawn']
const SENIORITY = ['junior', 'mid', 'senior', 'lead']
const REMOTE_TYPES = ['remote', 'hybrid', 'onsite', 'unknown']
const INTERVALS = ['yearly', 'monthly', 'weekly', 'daily', 'hourly']

const EVENT_LABELS: Record<string, string> = {
  discovered: '🆕 Discovered',
  reconfirmed: '✅ Still active',
  salary_changed: '💰 Salary changed',
  description_changed: '📝 Description changed',
  removed: '⚠️ Removed',
  reappeared: '♻️ Reappeared',
  applied: '📨 Applied',
  status_changed: '🔄 Status changed',
  dedup_alias: '🔗 Duplicate of another source',
  enriched: '✨ Enriched (backfill)',
  edited: '✏️ Edited by you',
}

const inputCls = 'bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm'

function EditRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-400 w-24 shrink-0">{label}</span>
      {children}
    </div>
  )
}

export default function JobDetail({ jobId, onClose }: { jobId: number; onClose: () => void }) {
  const queryClient = useQueryClient()
  const { data: job, isLoading } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => fetchJob(jobId),
  })
  const [notes, setNotes] = useState<string | null>(null)
  const [tagInput, setTagInput] = useState('')

  const mutation = useMutation({
    mutationFn: (patch: JobPatch) => patchJob(jobId, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job', jobId] })
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
      queryClient.invalidateQueries({ queryKey: ['events'] })
    },
  })

  const numOrUndef = (v: string) => (v === '' ? undefined : Number(v))

  return (
    <div className="fixed inset-0 bg-black/60 flex justify-end z-50" onClick={onClose}>
      <div
        className="w-full max-w-2xl h-full bg-slate-950 border-l border-slate-800 overflow-y-auto p-6 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        {isLoading || !job ? (
          <p className="text-slate-400">Loading…</p>
        ) : (
          <>
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold">{job.title}</h2>
                <p className="text-slate-400">
                  {job.company} · {job.city ?? job.remote_type ?? '—'} · {job.source}
                </p>
              </div>
              <button onClick={onClose} className="text-slate-400 hover:text-white text-xl">
                ✕
              </button>
            </div>

            <div className="flex items-center gap-3">
              <label className="text-sm text-slate-400">Status:</label>
              <select
                className={inputCls}
                value={job.app_status}
                onChange={(e) => mutation.mutate({ app_status: e.target.value })}
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <a
                href={job.url}
                target="_blank"
                rel="noreferrer"
                className="px-3 py-1 rounded bg-indigo-700 hover:bg-indigo-600 text-sm"
              >
                Open posting ↗
              </a>
            </div>

            <section className="rounded-lg bg-slate-900/50 border border-slate-800 p-3 space-y-2">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
                Details (editable)
              </h3>
              <EditRow label="Seniority">
                <select
                  className={inputCls}
                  value={job.seniority ?? ''}
                  onChange={(e) => mutation.mutate({ seniority: e.target.value || undefined })}
                >
                  <option value="">—</option>
                  {SENIORITY.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </EditRow>
              <EditRow label="Workplace">
                <select
                  className={inputCls}
                  value={job.remote_type ?? ''}
                  onChange={(e) => mutation.mutate({ remote_type: e.target.value || undefined })}
                >
                  <option value="">—</option>
                  {REMOTE_TYPES.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </EditRow>
              <EditRow label="City">
                <input
                  className={inputCls}
                  defaultValue={job.city ?? ''}
                  onBlur={(e) => {
                    if (e.target.value !== (job.city ?? ''))
                      mutation.mutate({ city: e.target.value || undefined })
                  }}
                />
              </EditRow>
              <EditRow label="Salary">
                <input
                  type="number"
                  className={`${inputCls} w-24`}
                  placeholder="min"
                  defaultValue={job.salary_min ?? ''}
                  onBlur={(e) => {
                    const v = numOrUndef(e.target.value)
                    if (v !== job.salary_min) mutation.mutate({ salary_min: v })
                  }}
                />
                <span className="text-slate-500">–</span>
                <input
                  type="number"
                  className={`${inputCls} w-24`}
                  placeholder="max"
                  defaultValue={job.salary_max ?? ''}
                  onBlur={(e) => {
                    const v = numOrUndef(e.target.value)
                    if (v !== job.salary_max) mutation.mutate({ salary_max: v })
                  }}
                />
                <input
                  className={`${inputCls} w-16`}
                  placeholder="EUR"
                  defaultValue={job.salary_currency ?? ''}
                  onBlur={(e) => {
                    if (e.target.value !== (job.salary_currency ?? ''))
                      mutation.mutate({ salary_currency: e.target.value || undefined })
                  }}
                />
                <select
                  className={inputCls}
                  value={job.salary_interval ?? 'yearly'}
                  onChange={(e) => mutation.mutate({ salary_interval: e.target.value })}
                >
                  {INTERVALS.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </EditRow>
              {(job.salary_annual_min || job.salary_annual_max) && (
                <p className="text-xs text-slate-500 pl-26">
                  ≈ {job.salary_annual_min?.toLocaleString() ?? '?'}–
                  {job.salary_annual_max?.toLocaleString() ?? '?'} {job.salary_currency ?? ''}/yr
                </p>
              )}
              <EditRow label="Tags">
                <div className="flex flex-wrap gap-1.5 items-center">
                  {job.tags.map((t) => (
                    <span key={t} className="px-2 py-0.5 rounded-full bg-slate-800 text-xs flex items-center gap-1">
                      {t}
                      <button
                        className="text-slate-400 hover:text-red-400"
                        onClick={() =>
                          mutation.mutate({ tags: job.tags.filter((x) => x !== t) })
                        }
                      >
                        ✕
                      </button>
                    </span>
                  ))}
                  <input
                    className={`${inputCls} w-24 text-xs`}
                    placeholder="+ tag"
                    value={tagInput}
                    onChange={(e) => setTagInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && tagInput.trim()) {
                        mutation.mutate({ tags: [...job.tags, tagInput.trim().toLowerCase()] })
                        setTagInput('')
                      }
                    }}
                  />
                </div>
              </EditRow>
            </section>

            <div>
              <label className="text-sm text-slate-400 block mb-1">Notes</label>
              <textarea
                className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm h-20"
                value={notes ?? job.app_notes ?? ''}
                onChange={(e) => setNotes(e.target.value)}
                onBlur={() => {
                  if (notes !== null && notes !== (job.app_notes ?? ''))
                    mutation.mutate({ app_notes: notes })
                }}
              />
            </div>

            {job.description && (
              <div className="text-sm">
                <h3 className="text-sm font-semibold text-slate-300 mb-2">Description</h3>
                <div className="description text-slate-300 max-h-[50vh] overflow-y-auto pr-2 rounded bg-slate-900/50 p-3">
                  <ReactMarkdown>{job.description}</ReactMarkdown>
                </div>
              </div>
            )}

            <div>
              <h3 className="text-sm font-semibold text-slate-300 mb-2">History</h3>
              <ul className="space-y-1 text-sm">
                {[...job.events].reverse().map((e) => (
                  <li key={e.id} className="flex gap-2 text-slate-400">
                    <span className="whitespace-nowrap">
                      {new Date(e.created_at).toLocaleString()}
                    </span>
                    <span>
                      {EVENT_LABELS[e.event_type] ?? e.event_type}
                      {e.event_type === 'edited' && e.payload && (
                        <span className="text-slate-500">
                          {' '}({String(e.payload.field)}: {JSON.stringify(e.payload.from)} →{' '}
                          {JSON.stringify(e.payload.to)})
                        </span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
