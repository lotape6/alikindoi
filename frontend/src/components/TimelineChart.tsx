import { useQuery } from '@tanstack/react-query'
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { fetchTimeline } from '../api'

export default function TimelineChart() {
  const { data } = useQuery({
    queryKey: ['timeline'],
    queryFn: fetchTimeline,
    refetchInterval: 60_000,
  })

  return (
    <section>
      <h2 className="text-lg font-semibold mb-2">Jobs over time (last 30 days)</h2>
      <div className="rounded-lg bg-slate-900 border border-slate-800 p-4 h-64">
        {data && data.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data}>
              <CartesianGrid stroke="#1e293b" />
              <XAxis dataKey="date" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis allowDecimals={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155' }}
                labelStyle={{ color: '#e2e8f0' }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="jobs_found" name="Found" fill="#6366f1" radius={[3, 3, 0, 0]} />
              <Bar dataKey="jobs_new" name="New" fill="#10b981" radius={[3, 3, 0, 0]} />
              <Line dataKey="removed" name="Removed" stroke="#f59e0b" strokeWidth={2} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-slate-400 text-sm">No activity recorded yet.</p>
        )}
      </div>
    </section>
  )
}
