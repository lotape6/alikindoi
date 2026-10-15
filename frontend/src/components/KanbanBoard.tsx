import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchJobs, patchJob, type Job } from '../api'
import { fitStyle, isDue, relativeDate, salaryEur, workplace } from '../format'

const COLUMNS: { key: string; label: string; accent: string }[] = [
  { key: 'saved', label: 'Shortlisted', accent: 'border-slate-400' },
  { key: 'applied', label: 'Applied', accent: 'border-indigo-500' },
  { key: 'interviewing', label: 'Interviewing', accent: 'border-amber-500' },
  { key: 'offer', label: 'Offer', accent: 'border-emerald-500' },
  { key: 'rejected', label: 'Rejected', accent: 'border-red-500' },
]

/** Application pipeline. Drag a card to another column to change its status. */
export default function KanbanBoard({ onSelect }: { onSelect: (id: number, ids: number[]) => void }) {
  const queryClient = useQueryClient()
  const { data } = useQuery({
    queryKey: ['pipeline'],
    queryFn: () =>
      fetchJobs({ app_status: COLUMNS.map((c) => c.key), page_size: 200, sort_by: 'next_action_at', sort_dir: 'asc' }),
  })
  const move = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => patchJob(id, { app_status: status }),
    onMutate: async ({ id, status }) => {
      await queryClient.cancelQueries({ queryKey: ['pipeline'] })
      queryClient.setQueryData<{ total: number; items: Job[] }>(['pipeline'], (old) =>
        old && { ...old, items: old.items.map((j) => (j.id === id ? { ...j, app_status: status } : j)) },
      )
    },
    onSettled: () => {
      for (const key of ['pipeline', 'jobs', 'views', 'stats']) queryClient.invalidateQueries({ queryKey: [key] })
    },
  })

  const jobs = data?.items ?? []
  const ids = jobs.map((j) => j.id)

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-3 xl:grid-cols-5">
      {COLUMNS.map((col) => {
        const cards = jobs.filter((j) => j.app_status === col.key)
        return (
          <div
            key={col.key}
            className={`min-h-64 rounded-lg border-t-2 ${col.accent} bg-slate-900/50 p-2 ring-1 ring-slate-800`}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              const id = Number(e.dataTransfer.getData('text/plain'))
              if (id) move.mutate({ id, status: col.key })
            }}
          >
            <div className="mb-2 flex items-center justify-between px-1">
              <span className="text-sm font-medium text-slate-200">{col.label}</span>
              <span className="text-xs text-slate-500">{cards.length}</span>
            </div>
            <div className="space-y-2">
              {cards.map((job) => (
                <div
                  key={job.id}
                  draggable
                  onDragStart={(e) => e.dataTransfer.setData('text/plain', String(job.id))}
                  onClick={() => onSelect(job.id, ids)}
                  className="cursor-grab space-y-1.5 rounded-md bg-slate-800/80 p-2.5 ring-1 ring-slate-700/50 hover:bg-slate-800 active:cursor-grabbing"
                >
                  <div className="flex items-start gap-2">
                    <p className="flex-1 text-sm font-medium leading-snug line-clamp-2">{job.title}</p>
                    <span className={`rounded px-1 text-[11px] font-semibold ${fitStyle(job.fit_score)}`}>
                      {job.fit_score != null ? Math.round(job.fit_score) : '–'}
                    </span>
                  </div>
                  <p className="truncate text-xs text-slate-400">
                    {job.company} · {workplace(job)}
                    {salaryEur(job) && ` · ${salaryEur(job)}`}
                  </p>
                  {job.next_action_at && (
                    <p className={`text-xs ${isDue(job.next_action_at) ? 'text-red-300' : 'text-slate-500'}`}>
                      ◷ {relativeDate(job.next_action_at)}
                      {job.next_action && ` · ${job.next_action}`}
                    </p>
                  )}
                  {!job.is_active && <p className="text-xs text-zinc-400">Position closed</p>}
                </div>
              ))}
              {cards.length === 0 && <p className="py-6 text-center text-xs text-slate-600">Drop a card here</p>}
            </div>
          </div>
        )
      })}
    </div>
  )
}
