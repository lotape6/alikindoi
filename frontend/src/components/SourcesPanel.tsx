import { useQuery } from '@tanstack/react-query'
import { fetchSources, type SourceInfo } from '../api'

function SourceCard({ source }: { source: SourceInfo }) {
  const state = source.running
    ? { label: 'running', cls: 'bg-amber-900 text-amber-300 animate-pulse' }
    : !source.enabled
      ? { label: 'disabled', cls: 'bg-slate-800 text-slate-400' }
      : !source.available
        ? { label: 'no credentials', cls: 'bg-red-900 text-red-300' }
        : { label: 'ready', cls: 'bg-emerald-900 text-emerald-300' }

  const last = source.last_run
  return (
    <div className="rounded-lg bg-slate-900 border border-slate-800 px-4 py-3 w-52">
      <div className="flex items-center justify-between">
        <span className="font-semibold">{source.name}</span>
        <span className={`px-2 py-0.5 rounded-full text-xs ${state.cls}`}>{state.label}</span>
      </div>
      <div className="text-xs text-slate-400 mt-1 space-y-0.5">
        <div>
          {source.kind} · min {source.min_interval_minutes} min
        </div>
        {last ? (
          <>
            <div>
              last: {new Date(last.at).toLocaleString()} —{' '}
              <span className={last.status === 'ok' ? 'text-emerald-400' : last.status === 'failed' ? 'text-red-400' : 'text-sky-400'}>
                {last.status}
              </span>
            </div>
            {last.status === 'ok' && (
              <div>
                found {last.jobs_found ?? 0} · new {last.jobs_new ?? 0}
              </div>
            )}
            {last.error && (
              <div className="text-red-400 truncate" title={last.error}>
                {last.error}
              </div>
            )}
          </>
        ) : (
          <div>never run</div>
        )}
      </div>
    </div>
  )
}

export default function SourcesPanel() {
  const { data: sources } = useQuery({
    queryKey: ['sources'],
    queryFn: fetchSources,
    refetchInterval: 10_000,
  })
  return (
    <section>
      <h2 className="text-lg font-semibold mb-2">Sources</h2>
      <div className="flex flex-wrap gap-3">
        {sources?.map((s) => <SourceCard key={s.name} source={s} />)}
      </div>
      <p className="text-xs text-slate-500 mt-1">
        Enable/disable sources and provide API credentials via config.yaml / .env
        (see TODOs.md).
      </p>
    </section>
  )
}
