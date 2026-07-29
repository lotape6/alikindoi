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

function salary(job: Job): string {
  if (!job.salary_annual_min && !job.salary_annual_max) return '—'
  const lo = job.salary_annual_min ? `${Math.round(job.salary_annual_min / 1000)}k` : '?'
  const hi = job.salary_annual_max ? `${Math.round(job.salary_annual_max / 1000)}k` : '?'
  return `${lo}–${hi} ${job.salary_currency ?? ''}`
}

export default function JobsTable({
  jobs,
  onSelect,
}: {
  jobs: Job[]
  onSelect: (id: number) => void
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-800">
      <table className="w-full text-sm">
        <thead className="bg-slate-900 text-slate-400 text-left">
          <tr>
            {['', 'Title', 'Company', 'Location', 'Seniority', 'Salary/yr', 'Status', 'Source', 'Posted'].map(
              (h) => (
                <th key={h} className="px-3 py-2 font-medium">
                  {h}
                </th>
              ),
            )}
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
              <td className="px-3 py-2 whitespace-nowrap">
                {job.app_status === 'new' && job.is_active && <span title="New">🆕</span>}
                {!job.is_active && <span title="Removed">⚠️</span>}
              </td>
              <td className="px-3 py-2 font-medium max-w-xs truncate">{job.title}</td>
              <td className="px-3 py-2 max-w-[10rem] truncate">{job.company}</td>
              <td className="px-3 py-2 whitespace-nowrap">
                {job.city ?? (job.remote_type === 'remote' ? 'Remote' : '—')}
                {job.remote_type && job.remote_type !== 'onsite' && (
                  <span className="ml-1 text-xs text-slate-400">({job.remote_type})</span>
                )}
              </td>
              <td className="px-3 py-2">{job.seniority ?? '—'}</td>
              <td className="px-3 py-2 whitespace-nowrap">{salary(job)}</td>
              <td className="px-3 py-2">
                <span
                  className={`px-2 py-0.5 rounded-full text-xs ${STATUS_COLORS[job.app_status] ?? ''}`}
                >
                  {job.app_status}
                </span>
              </td>
              <td className="px-3 py-2 text-slate-400">{job.source}</td>
              <td className="px-3 py-2 text-slate-400 whitespace-nowrap">
                {job.date_posted ?? '—'}
              </td>
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
