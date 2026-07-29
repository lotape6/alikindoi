import { useCallback, useRef, useState } from 'react'
import type { Job } from '../api'

const STATUS_COLORS: Record<string, string> = {
  new: 'bg-sky-900 text-sky-300',
  saved: 'bg-slate-700 text-slate-200',
  applied: 'bg-indigo-900 text-indigo-300',
  interviewing: 'bg-amber-900 text-amber-300',
  offer: 'bg-emerald-900 text-emerald-300',
  rejected: 'bg-red-900 text-red-300',
  withdrawn: 'bg-slate-800 text-slate-400',
}

interface Column {
  key: string
  label: string
  sortable?: string
  defaultWidth: number
  render: (job: Job) => React.ReactNode
}

function salary(job: Job): string {
  if (!job.salary_annual_min && !job.salary_annual_max) return '—'
  const lo = job.salary_annual_min ? `${Math.round(job.salary_annual_min / 1000)}k` : '?'
  const hi = job.salary_annual_max ? `${Math.round(job.salary_annual_max / 1000)}k` : '?'
  return `${lo}–${hi} ${job.salary_currency ?? ''}`
}

const COLUMNS: Column[] = [
  {
    key: 'badges', label: '', defaultWidth: 40,
    render: (j) => (
      <>
        {j.app_status === 'new' && j.is_active && <span title="New">🆕</span>}
        {!j.is_active && <span title="Removed">⚠️</span>}
      </>
    ),
  },
  { key: 'title', label: 'Title', sortable: 'title', defaultWidth: 240, render: (j) => <span className="font-medium">{j.title}</span> },
  { key: 'company', label: 'Company', sortable: 'company', defaultWidth: 140, render: (j) => j.company },
  {
    key: 'location', label: 'Location', sortable: 'city', defaultWidth: 130,
    render: (j) => (
      <>
        {j.city ?? (j.remote_type === 'remote' ? 'Remote' : '—')}
        {j.remote_type && j.remote_type !== 'onsite' && (
          <span className="ml-1 text-xs text-slate-400">({j.remote_type})</span>
        )}
      </>
    ),
  },
  { key: 'seniority', label: 'Seniority', sortable: 'seniority', defaultWidth: 90, render: (j) => j.seniority ?? '—' },
  { key: 'salary', label: 'Salary/yr', sortable: 'salary_annual_max', defaultWidth: 110, render: (j) => salary(j) },
  {
    key: 'status', label: 'Status', defaultWidth: 100,
    render: (j) => (
      <span className={`px-2 py-0.5 rounded-full text-xs ${STATUS_COLORS[j.app_status] ?? ''}`}>
        {j.app_status}
      </span>
    ),
  },
  { key: 'source', label: 'Source', sortable: 'source', defaultWidth: 90, render: (j) => <span className="text-slate-400">{j.source}</span> },
  { key: 'posted', label: 'Posted', sortable: 'date_posted', defaultWidth: 100, render: (j) => <span className="text-slate-400">{j.date_posted ?? '—'}</span> },
]

export default function JobsTable({
  jobs,
  onSelect,
  sortBy,
  sortDir,
  onSort,
}: {
  jobs: Job[]
  onSelect: (id: number) => void
  sortBy?: string
  sortDir?: 'asc' | 'desc'
  onSort: (column: string) => void
}) {
  const [widths, setWidths] = useState<Record<string, number>>(
    Object.fromEntries(COLUMNS.map((c) => [c.key, c.defaultWidth])),
  )
  const dragRef = useRef<{ key: string; startX: number; startWidth: number } | null>(null)

  const onMouseDown = useCallback(
    (key: string) => (e: React.MouseEvent) => {
      e.preventDefault()
      e.stopPropagation()
      dragRef.current = { key, startX: e.clientX, startWidth: widths[key] }
      const onMove = (ev: MouseEvent) => {
        const drag = dragRef.current
        if (!drag) return
        const newWidth = Math.max(50, drag.startWidth + ev.clientX - drag.startX)
        setWidths((w) => ({ ...w, [drag.key]: newWidth }))
      }
      const onUp = () => {
        dragRef.current = null
        window.removeEventListener('mousemove', onMove)
        window.removeEventListener('mouseup', onUp)
      }
      window.addEventListener('mousemove', onMove)
      window.addEventListener('mouseup', onUp)
    },
    [widths],
  )

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-800">
      <table className="text-sm table-fixed" style={{ width: Object.values(widths).reduce((a, b) => a + b, 0) }}>
        <thead className="bg-slate-900 text-slate-400 text-left">
          <tr>
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                style={{ width: widths[col.key] }}
                className="px-3 py-2 font-medium relative select-none"
              >
                <span
                  className={col.sortable ? 'cursor-pointer hover:text-slate-200' : ''}
                  onClick={() => col.sortable && onSort(col.sortable)}
                >
                  {col.label}
                  {col.sortable && sortBy === col.sortable && (
                    <span className="ml-1">{sortDir === 'asc' ? '▲' : '▼'}</span>
                  )}
                </span>
                <span
                  onMouseDown={onMouseDown(col.key)}
                  className="absolute right-0 top-0 h-full w-1.5 cursor-col-resize hover:bg-indigo-500"
                />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr
              key={job.id}
              onClick={() => onSelect(job.id)}
              className={`border-t border-slate-800 cursor-pointer hover:bg-slate-900 ${
                job.is_active ? '' : 'opacity-50'
              }`}
            >
              {COLUMNS.map((col) => (
                <td key={col.key} className="px-3 py-2 truncate" style={{ width: widths[col.key] }}>
                  {col.render(job)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {jobs.length === 0 && (
        <p className="px-4 py-6 text-center text-slate-400">No jobs match these filters.</p>
      )}
    </div>
  )
}
