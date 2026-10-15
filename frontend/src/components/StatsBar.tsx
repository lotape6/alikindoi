import { useQuery } from '@tanstack/react-query'
import { fetchStats } from '../api'

export default function StatsBar({ onNewOnly }: { onNewOnly: () => void }) {
  const { data } = useQuery({
    queryKey: ['stats'],
    queryFn: fetchStats,
    refetchInterval: 60_000,
  })
  if (!data) return null

  const cards = [
    { label: 'Active', value: data.active, className: 'text-emerald-400' },
    { label: 'New', value: data.new, className: 'text-sky-400', onClick: onNewOnly },
    { label: 'Removed', value: data.removed, className: 'text-amber-400' },
    {
      label: 'Avg max salary',
      value: data.salary_avg_max ? `€${Math.round(data.salary_avg_max).toLocaleString()}` : '—',
      className: 'text-violet-400',
    },
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {cards.map((c) => (
        <button
          key={c.label}
          onClick={c.onClick}
          className="rounded-lg bg-slate-900 border border-slate-800 px-4 py-3 text-left hover:border-slate-600 transition"
        >
          <div className={`text-2xl font-bold ${c.className}`}>{c.value}</div>
          <div className="text-xs text-slate-400 uppercase tracking-wide">{c.label}</div>
        </button>
      ))}
    </div>
  )
}
