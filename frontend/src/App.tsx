import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchJobs, type JobFilters } from './api'
import StatsBar from './components/StatsBar'
import FilterBar from './components/FilterBar'
import JobsTable from './components/JobsTable'
import JobDetail from './components/JobDetail'
import AdminPanel from './components/AdminPanel'

export default function App() {
  const [view, setView] = useState<'jobs' | 'admin'>('jobs')
  const [filters, setFilters] = useState<JobFilters>({ page: 1, page_size: 50 })
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['jobs', filters],
    queryFn: () => fetchJobs(filters),
    enabled: view === 'jobs',
  })

  const update = (patch: Partial<JobFilters>) =>
    setFilters((f) => ({ ...f, ...patch, page: 1 }))

  const totalPages = data ? Math.max(1, Math.ceil(data.total / (filters.page_size ?? 50))) : 1

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-bold tracking-tight">
          Alikindoi <span className="text-slate-400 font-normal">— job tracker</span>
        </h1>
        <nav className="flex gap-2">
          {(['jobs', 'admin'] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-3 py-1.5 rounded text-sm ${
                view === v ? 'bg-indigo-700' : 'bg-slate-800 hover:bg-slate-700'
              }`}
            >
              {v === 'jobs' ? '💼 Jobs' : '⚙️ Scraping'}
            </button>
          ))}
        </nav>
      </header>

      <main className="px-6 py-4 space-y-4">
        {view === 'admin' ? (
          <AdminPanel />
        ) : (
          <>
            <StatsBar onNewOnly={() => update({ new_only: !filters.new_only, removed: false })} />
            <FilterBar filters={filters} onChange={update} />

            {isLoading && <p className="text-slate-400">Loading jobs…</p>}
            {isError && <p className="text-red-400">Error: {(error as Error).message}</p>}
            {data && (
              <>
                <p className="text-sm text-slate-400">{data.total} jobs</p>
                <JobsTable jobs={data.items} onSelect={setSelectedId} />
                <div className="flex items-center gap-3 text-sm">
                  <button
                    className="px-3 py-1 rounded bg-slate-800 disabled:opacity-40"
                    disabled={(filters.page ?? 1) <= 1}
                    onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) - 1 }))}
                  >
                    ← Prev
                  </button>
                  <span className="text-slate-400">
                    Page {filters.page ?? 1} / {totalPages}
                  </span>
                  <button
                    className="px-3 py-1 rounded bg-slate-800 disabled:opacity-40"
                    disabled={(filters.page ?? 1) >= totalPages}
                    onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) + 1 }))}
                  >
                    Next →
                  </button>
                </div>
              </>
            )}
          </>
        )}
      </main>

      {selectedId !== null && (
        <JobDetail jobId={selectedId} onClose={() => setSelectedId(null)} />
      )}
    </div>
  )
}
