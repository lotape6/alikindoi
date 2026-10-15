import { useMutation, useQueryClient } from '@tanstack/react-query'
import { patchJob, type Job } from '../api'
import {
  CLOSED_REASON, STATUS_LABEL, STATUS_STYLE, fitStyle, isDue, locationText, relativeDate, salaryEur,
  salaryOriginal, sourceLabel, workplace,
} from '../format'

interface Props {
  jobs: Job[]
  selectedId: number | null
  onSelect: (id: number) => void
  sortBy?: string
  sortDir?: 'asc' | 'desc'
  onSort: (column: string) => void
  /** Fewer columns, used while the detail panel takes half the screen. */
  compact?: boolean
}

const COMPACT_HIDDEN = new Set(['where', 'boards', 'next', 'found'])

const COLUMNS: { key: string; label: string; sort?: string; className?: string }[] = [
  { key: 'star', label: '', className: 'w-8' },
  { key: 'fit', label: 'Fit', sort: 'fit_score', className: 'w-14' },
  { key: 'role', label: 'Position', sort: 'title' },
  { key: 'where', label: 'Workplace', sort: 'remote_type', className: 'w-48' },
  { key: 'salary', label: 'Salary (EUR/yr)', sort: 'salary_annual_max', className: 'w-32' },
  { key: 'boards', label: 'Boards', className: 'w-36' },
  { key: 'status', label: 'Status', className: 'w-28' },
  { key: 'next', label: 'Next step', sort: 'next_action_at', className: 'w-36' },
  { key: 'found', label: 'Found', sort: 'first_seen_at', className: 'w-20' },
]

export default function JobsTable({ jobs, selectedId, onSelect, sortBy, sortDir, onSort, compact }: Props) {
  const show = (key: string) => !compact || !COMPACT_HIDDEN.has(key)
  const queryClient = useQueryClient()
  const star = useMutation({
    mutationFn: (job: Job) => patchJob(job.id, { starred: !job.starred }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['views'] })
    },
  })

  if (jobs.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-800 py-16 text-center text-sm text-slate-500">
        No positions match this view.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-lg ring-1 ring-slate-800">
      <table className="w-full text-sm">
        <thead className="bg-slate-900/80 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            {COLUMNS.filter((c) => show(c.key)).map((c) => (
              <th key={c.key} className={`whitespace-nowrap px-3 py-2.5 font-medium ${c.className ?? ''}`}>
                {c.sort ? (
                  <button onClick={() => onSort(c.sort!)} className="uppercase tracking-wide hover:text-slate-300">
                    {c.label}
                    {sortBy === c.sort && <span className="ml-1">{sortDir === 'asc' ? '↑' : '↓'}</span>}
                  </button>
                ) : (
                  c.label
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/80">
          {jobs.map((job) => {
            const selected = job.id === selectedId
            const salary = salaryEur(job)
            return (
              <tr
                key={job.id}
                data-job-id={job.id}
                onClick={() => onSelect(job.id)}
                className={`cursor-pointer ${selected ? 'bg-indigo-500/10' : 'hover:bg-slate-900/70'} ${
                  job.is_active ? '' : 'opacity-60'
                }`}
              >
                <td className="px-3 py-2.5">
                  <button
                    aria-label={job.starred ? 'Unstar' : 'Star'}
                    onClick={(e) => {
                      e.stopPropagation()
                      star.mutate(job)
                    }}
                    className={job.starred ? 'text-amber-400' : 'text-slate-600 hover:text-slate-400'}
                  >
                    {job.starred ? '★' : '☆'}
                  </button>
                </td>
                <td className="px-3 py-2.5">
                  <span
                    title={job.fit_notes?.join('\n') || 'Fit against your search criteria'}
                    className={`inline-block min-w-9 rounded px-1.5 py-0.5 text-center text-xs font-semibold tabular-nums ${fitStyle(job.fit_score)}`}
                  >
                    {job.fit_score != null ? Math.round(job.fit_score) : '–'}
                  </span>
                </td>
                <td className="px-3 py-2.5 max-w-0">
                  <div className="flex items-center gap-2">
                    {job.app_status === 'new' && job.is_active && (
                      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-sky-400" title="Not reviewed yet" />
                    )}
                    <p className="truncate font-medium text-slate-100">{job.title}</p>
                  </div>
                  <p className="truncate text-xs text-slate-400">
                    {job.company}
                    {job.seniority && <span className="text-slate-500"> · {job.seniority}</span>}
                  </p>
                </td>
                {show('where') && <td className="px-3 py-2.5">
                  <p className="text-slate-200">{workplace(job)}</p>
                  <p className="truncate text-xs text-slate-500 max-w-44" title={job.region ?? undefined}>
                    {locationText(job)}
                  </p>
                </td>}
                <td className="whitespace-nowrap px-3 py-2.5 tabular-nums" title={salaryOriginal(job) ?? 'Not stated'}>
                  {salary ?? <span className="text-slate-600">not stated</span>}
                </td>
                {show('boards') && <td className="px-3 py-2.5">
                  <div className="flex flex-wrap gap-1">
                    {job.sources.map((s) => (
                      <span key={s} className="rounded bg-slate-800 px-1.5 py-0.5 text-[11px] text-slate-300">
                        {sourceLabel(s)}
                      </span>
                    ))}
                  </div>
                </td>}
                <td className="whitespace-nowrap px-3 py-2.5">
                  {job.is_active ? (
                    <span className={`rounded-full px-2 py-0.5 text-xs ring-1 ${STATUS_STYLE[job.app_status] ?? ''}`}>
                      {STATUS_LABEL[job.app_status] ?? job.app_status}
                    </span>
                  ) : (
                    <span
                      title={CLOSED_REASON[job.closed_reason ?? ''] ?? undefined}
                      className="rounded-full bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400 ring-1 ring-zinc-700"
                    >
                      Closed
                    </span>
                  )}
                </td>
                {show('next') && <td className="px-3 py-2.5">
                  {job.next_action_at ? (
                    <div className={isDue(job.next_action_at) ? 'text-red-300' : 'text-slate-300'}>
                      <p className="text-xs font-medium">{relativeDate(job.next_action_at)}</p>
                      <p className="truncate text-xs text-slate-500 max-w-32">{job.next_action}</p>
                    </div>
                  ) : (
                    <span className="text-slate-700">—</span>
                  )}
                </td>}
                {show('found') && <td className="whitespace-nowrap px-3 py-2.5 text-xs text-slate-400" title={job.first_seen_at}>
                  {relativeDate(job.first_seen_at)}
                </td>}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
