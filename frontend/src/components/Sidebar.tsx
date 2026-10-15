import { useQuery } from '@tanstack/react-query'
import { fetchViews, type ViewCounts } from '../api'
import type { View } from '../urlState'

type Item = { view: View; label: string; icon: string; count?: keyof ViewCounts; alert?: boolean }

const GROUPS: { title: string; items: Item[] }[] = [
  {
    title: 'Discover',
    items: [
      { view: 'inbox', label: 'Inbox', icon: '◉', count: 'inbox' },
      { view: 'all', label: 'All open positions', icon: '≡', count: 'all' },
      { view: 'starred', label: 'Starred', icon: '★', count: 'starred' },
      { view: 'follow_up', label: 'Follow-ups due', icon: '◷', count: 'follow_up', alert: true },
    ],
  },
  {
    title: 'Pipeline',
    items: [
      { view: 'pipeline', label: 'Board', icon: '▦' },
      { view: 'saved', label: 'Shortlisted', icon: '◇', count: 'saved' },
      { view: 'applied', label: 'Applied', icon: '↗', count: 'applied' },
      { view: 'interviewing', label: 'Interviewing', icon: '◎', count: 'interviewing' },
      { view: 'offer', label: 'Offers', icon: '✓', count: 'offer' },
    ],
  },
  {
    title: 'History',
    items: [
      { view: 'archived', label: 'Rejected & withdrawn', icon: '×', count: 'archived' },
      { view: 'closed', label: 'Closed positions', icon: '⊘', count: 'closed' },
      { view: 'activity', label: 'Activity', icon: '↻' },
    ],
  },
  {
    title: 'Setup',
    items: [
      { view: 'settings', label: 'Search criteria', icon: '◈' },
      { view: 'sources', label: 'Boards & runs', icon: '⇅' },
    ],
  },
]

export default function Sidebar({ view, onSelect }: { view: View; onSelect: (v: View) => void }) {
  const { data: counts } = useQuery({ queryKey: ['views'], queryFn: fetchViews, refetchInterval: 60_000 })

  return (
    <nav className="w-60 shrink-0 border-r border-slate-800 bg-slate-950/80 h-screen sticky top-0 overflow-y-auto">
      <div className="px-5 py-5">
        <p className="text-lg font-semibold tracking-tight">Alikindoi</p>
        <p className="text-xs text-slate-500">Job search & application tracker</p>
      </div>
      {GROUPS.map((group) => (
        <div key={group.title} className="px-3 pb-4">
          <p className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">{group.title}</p>
          {group.items.map((item) => {
            const n = item.count && counts ? counts[item.count] : undefined
            const active = view === item.view
            return (
              <button
                key={item.view}
                onClick={() => onSelect(item.view)}
                className={`w-full flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm text-left ${
                  active ? 'bg-indigo-600/20 text-indigo-200' : 'text-slate-300 hover:bg-slate-800/70'
                }`}
              >
                <span className="w-4 text-center text-slate-500">{item.icon}</span>
                <span className="flex-1 truncate">{item.label}</span>
                {n !== undefined && n > 0 && (
                  <span
                    className={`text-xs tabular-nums rounded px-1.5 ${
                      item.alert ? 'bg-red-500/20 text-red-300' : 'text-slate-500'
                    }`}
                  >
                    {n}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      ))}
    </nav>
  )
}
