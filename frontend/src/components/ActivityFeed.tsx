import { useQuery } from '@tanstack/react-query'
import { fetchEvents } from '../api'

const EVENT_LABELS: Record<string, string> = {
  discovered: '🆕',
  reconfirmed: '✅',
  salary_changed: '💰',
  description_changed: '📝',
  removed: '⚠️',
  reappeared: '♻️',
  applied: '📨',
  status_changed: '🔄',
  dedup_alias: '🔗',
  enriched: '✨',
  edited: '✏️',
}

export default function ActivityFeed({ onSelect }: { onSelect: (id: number) => void }) {
  const { data: events } = useQuery({
    queryKey: ['events'],
    queryFn: fetchEvents,
    refetchInterval: 30_000,
  })

  return (
    <section>
      <h2 className="text-lg font-semibold mb-2">Activity</h2>
      <div className="rounded-lg border border-slate-800 divide-y divide-slate-800">
        {events?.map((e) => (
          <button
            key={e.id}
            onClick={() => onSelect(e.job_id)}
            className="w-full flex items-center gap-3 px-4 py-2 text-sm hover:bg-slate-900 text-left"
          >
            <span className="w-6 text-center">{EVENT_LABELS[e.event_type] ?? '•'}</span>
            <span className="text-slate-400 whitespace-nowrap text-xs">
              {new Date(e.created_at).toLocaleString()}
            </span>
            <span className="font-medium truncate">
              {e.job_title} <span className="text-slate-400">@ {e.job_company}</span>
            </span>
            <span className="text-slate-500 text-xs ml-auto whitespace-nowrap">
              {e.event_type}
              {e.event_type === 'edited' && e.payload ? ` (${String(e.payload.field)})` : ''}
            </span>
          </button>
        ))}
        {events?.length === 0 && (
          <p className="px-4 py-6 text-center text-slate-400">No activity yet.</p>
        )}
      </div>
    </section>
  )
}
