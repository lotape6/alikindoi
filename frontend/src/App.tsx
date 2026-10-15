import { useEffect, useMemo, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { fetchJobs, type JobFilters } from './api'
import { useUrlState, type View } from './urlState'
import Sidebar from './components/Sidebar'
import FilterBar from './components/FilterBar'
import JobsTable from './components/JobsTable'
import KanbanBoard from './components/KanbanBoard'
import JobDetail from './components/JobDetail'
import AdminPanel from './components/AdminPanel'
import ActivityFeed from './components/ActivityFeed'
import CriteriaEditor from './components/CriteriaEditor'

const PAGE_SIZE = 50

// What each list view shows, before the user's own filters.
const VIEW_FILTERS: Partial<Record<View, JobFilters>> = {
  inbox: { app_status: ['new'] },
  all: {},
  starred: { starred: true },
  follow_up: { follow_up_due: true, sort_by: 'next_action_at', sort_dir: 'asc' },
  saved: { app_status: ['saved'] },
  applied: { app_status: ['applied'] },
  interviewing: { app_status: ['interviewing'] },
  offer: { app_status: ['offer'] },
  archived: { app_status: ['rejected', 'withdrawn'] },
  closed: { removed: true, sort_by: 'closed_at', sort_dir: 'desc' },
}

const VIEW_TITLE: Record<View, [string, string]> = {
  inbox: ['Inbox', 'New positions you have not reviewed yet, best fit first.'],
  all: ['All open positions', 'Every open position that matches your criteria.'],
  starred: ['Starred', 'Positions you marked to come back to.'],
  follow_up: ['Follow-ups due', 'Next steps due today or overdue.'],
  pipeline: ['Pipeline', 'Drag a card to move it to another stage.'],
  saved: ['Shortlisted', 'Positions you want to apply to.'],
  applied: ['Applied', 'Waiting for an answer.'],
  interviewing: ['Interviewing', 'Processes in progress.'],
  offer: ['Offers', ''],
  archived: ['Rejected & withdrawn', ''],
  closed: ['Closed positions', 'No longer listed on any board, expired, or closed by you.'],
  activity: ['Activity', 'Everything that changed, newest first.'],
  sources: ['Boards & runs', 'Search profiles, boards and the history of every search.'],
  settings: ['Search criteria', ''],
}

export default function App() {
  const [{ view, filters, job }, setUrl] = useUrlState()
  const [navIds, setNavIds] = useState<number[]>([])
  const isList = view in VIEW_FILTERS

  const query = useMemo<JobFilters>(
    () => ({ sort_by: 'fit_score', sort_dir: 'desc', ...VIEW_FILTERS[view], ...filters, page_size: PAGE_SIZE }),
    [view, filters],
  )
  const { data, isLoading, isError, error, isFetching } = useQuery({
    queryKey: ['jobs', query],
    queryFn: () => fetchJobs(query),
    enabled: isList,
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
  })

  const listIds = useMemo(() => data?.items.map((j) => j.id) ?? [], [data])
  const ids = view === 'pipeline' ? navIds : listIds
  const index = job ? ids.indexOf(job) : -1
  const open = (id: number | null) => setUrl({ job: id }, id !== null && job === null)
  const step = (delta: number) => {
    const next = ids[(index < 0 ? (delta > 0 ? -1 : ids.length) : index) + delta]
    if (next) {
      open(next)
      document.querySelector(`[data-job-id="${next}"]`)?.scrollIntoView({ block: 'nearest' })
    }
  }

  // Keyboard: j/k move between positions, Enter opens, Esc closes, / searches.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) {
        if (e.key === 'Escape') target.blur()
        return
      }
      if (e.key === 'Escape' && job) open(null)
      else if (e.key === 'j' || e.key === 'ArrowDown') step(1)
      else if (e.key === 'k' || e.key === 'ArrowUp') step(-1)
      else if (e.key === '/') {
        e.preventDefault()
        document.getElementById('job-search')?.focus()
      } else return
      e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const setFilters = (patch: Partial<JobFilters>) => setUrl({ filters: { ...filters, ...patch, page: 1 } })
  const page = filters.page ?? 1
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1
  const [title, subtitle] = VIEW_TITLE[view] ?? VIEW_TITLE.inbox

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      <Sidebar view={view} onSelect={(v) => setUrl({ view: v, job: null, filters: v in VIEW_FILTERS ? filters : {} }, true)} />

      <main className={`min-w-0 flex-1 px-8 py-6 ${job ? '2xl:pr-[44rem]' : ''}`}>
        {view !== 'settings' && (
          <div className="mb-5">
            <h1 className="text-xl font-semibold">{title}</h1>
            {subtitle && <p className="mt-0.5 text-sm text-slate-400">{subtitle}</p>}
          </div>
        )}

        {view === 'settings' && <CriteriaEditor />}
        {view === 'sources' && <AdminPanel />}
        {view === 'activity' && <ActivityFeed onSelect={(id) => open(id)} />}
        {view === 'pipeline' && (
          <KanbanBoard
            onSelect={(id, all) => {
              setNavIds(all)
              open(id)
            }}
          />
        )}

        {isList && (
          <div className="space-y-4">
            <FilterBar
              filters={query}
              onChange={setFilters}
              onReset={() => setUrl({ filters: {} })}
              total={data?.total}
            />
            {isLoading && <p className="text-slate-400">Loading positions…</p>}
            {isError && <p className="text-red-400">Could not load positions: {(error as Error).message}</p>}
            {data && (
              <div className={isFetching ? 'opacity-80 transition-opacity' : ''}>
                <JobsTable
                  jobs={data.items}
                  selectedId={job}
                  onSelect={open}
                  compact={job !== null}
                  sortBy={query.sort_by}
                  sortDir={query.sort_dir}
                  onSort={(col) =>
                    setFilters({ sort_by: col, sort_dir: query.sort_by === col && query.sort_dir === 'desc' ? 'asc' : 'desc' })
                  }
                />
                {totalPages > 1 && (
                  <div className="mt-3 flex items-center gap-3 text-sm">
                    <button
                      className="rounded-md bg-slate-800 px-3 py-1 disabled:opacity-40"
                      disabled={page <= 1}
                      onClick={() => setUrl({ filters: { ...filters, page: page - 1 } })}
                    >
                      ← Previous
                    </button>
                    <span className="text-slate-400">Page {page} of {totalPages}</span>
                    <button
                      className="rounded-md bg-slate-800 px-3 py-1 disabled:opacity-40"
                      disabled={page >= totalPages}
                      onClick={() => setUrl({ filters: { ...filters, page: page + 1 } })}
                    >
                      Next →
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>

      {job !== null && (
        <JobDetail
          jobId={job}
          onClose={() => open(null)}
          onPrev={index > 0 ? () => step(-1) : undefined}
          onNext={index >= 0 && index < ids.length - 1 ? () => step(1) : undefined}
          position={index >= 0 ? `${index + 1} of ${ids.length}` : undefined}
        />
      )}
    </div>
  )
}
