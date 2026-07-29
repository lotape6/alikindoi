import { useMutation, useQueryClient } from '@tanstack/react-query'
import { patchJob, type Job } from '../api'

const COLUMNS: { key: string; label: string; accent: string }[] = [
  { key: 'new', label: '🆕 New', accent: 'border-sky-500' },
  { key: 'saved', label: '🔖 Saved', accent: 'border-slate-500' },
  { key: 'applied', label: '📨 Applied', accent: 'border-indigo-500' },
  { key: 'interviewing', label: '💬 Interviewing', accent: 'border-amber-500' },
  { key: 'offer', label: '🎉 Offer', accent: 'border-emerald-500' },
  { key: 'rejected', label: '❌ Rejected', accent: 'border-red-500' },
]

function salary(job: Job): string {
  if (!job.salary_annual_max) return ''
  return `€${Math.round(job.salary_annual_max / 1000)}k`
}

export default function KanbanBoard({
  jobs,
  onSelect,
}: {
  jobs: Job[]
  onSelect: (id: number) => void
}) {
  const queryClient = useQueryClient()
  const move = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      patchJob(id, { app_status: status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
  })

  const onDrop = (e: React.DragEvent, status: string) => {
    const id = Number(e.dataTransfer.getData('text/plain'))
    if (id) move.mutate({ id, status })
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
      {COLUMNS.map((col) => {
        const cards = jobs.filter((j) => j.app_status === col.key)
        return (
          <div
            key={col.key}
            className={`rounded-lg bg-slate-900/60 border-t-2 ${col.accent} border-x border-b border-slate-800 p-2 min-h-40`}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => onDrop(e, col.key)}
          >
            <div className="flex items-center justify-between px-1 mb-2">
              <span className="text-xs font-semibold text-slate-300">{col.label}</span>
              <span className="text-xs text-slate-500">{cards.length}</span>
            </div>
            <div className="space-y-2">
              {cards.map((job) => (
                <div
                  key={job.id}
                  draggable
                  onDragStart={(e) => e.dataTransfer.setData('text/plain', String(job.id))}
                  onClick={() => onSelect(job.id)}
                  className="rounded bg-slate-800 hover:bg-slate-700 p-2 cursor-grab active:cursor-grabbing"
                >
                  <p className="text-xs font-medium leading-tight line-clamp-2">{job.title}</p>
                  <p className="text-xs text-slate-400 mt-1 truncate">
                    {job.company} · {job.city ?? job.remote_type ?? '—'} {salary(job)}
                  </p>
                </div>
              ))}
              {cards.length === 0 && (
                <p className="text-xs text-slate-600 text-center py-4">empty</p>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
