import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchJob, patchJob } from '../api'

const STATUSES = ['new', 'saved', 'applied', 'interviewing', 'offer', 'rejected', 'withdrawn']

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
}

export default function JobDetail({ jobId, onClose }: { jobId: number; onClose: () => void }) {
  const queryClient = useQueryClient()
  const { data: job, isLoading } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => fetchJob(jobId),
  })
  const [notes, setNotes] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (patch: { app_status?: string; app_notes?: string }) => patchJob(jobId, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job', jobId] })
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
  })

  return (
    <div
      className="fixed inset-0 bg-black/60 flex justify-end z-50"
      onClick={onClose}
    >
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
                  {job.company} · {job.city ?? job.remote_type ?? '—'} · {job.seniority ?? '—'} ·{' '}
                  {job.source}
                </p>
              </div>
              <button onClick={onClose} className="text-slate-400 hover:text-white text-xl">
                ✕
              </button>
            </div>

            <div className="flex flex-wrap gap-2">
              {job.tags.map((t) => (
                <span key={t} className="px-2 py-0.5 rounded-full bg-slate-800 text-xs">
                  {t}
                </span>
              ))}
            </div>

            <div className="flex items-center gap-3">
              <label className="text-sm text-slate-400">Status:</label>
              <select
                className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm"
                value={job.app_status}
                onChange={(e) => mutation.mutate({ app_status: e.target.value })}
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
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
              <details className="text-sm">
                <summary className="cursor-pointer text-slate-400">Description</summary>
                <p className="mt-2 whitespace-pre-wrap text-slate-300 max-h-96 overflow-y-auto">
                  {job.description}
                </p>
              </details>
            )}

            <div>
              <h3 className="text-sm font-semibold text-slate-300 mb-2">History</h3>
              <ul className="space-y-1 text-sm">
                {[...job.events].reverse().map((e) => (
                  <li key={e.id} className="flex gap-2 text-slate-400">
                    <span className="whitespace-nowrap">
                      {new Date(e.created_at).toLocaleString()}
                    </span>
                    <span>{EVENT_LABELS[e.event_type] ?? e.event_type}</span>
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
