import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchConfig,
  fetchRuns,
  fetchScrapeStatus,
  patchProfile,
  triggerScrape,
  type SearchProfile,
} from '../api'

const RUN_STATUS: Record<string, string> = {
  ok: 'text-emerald-400',
  failed: 'text-red-400',
  skipped_rate_limit: 'text-sky-400',
}

function ProfileRow({ profile }: { profile: SearchProfile }) {
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: (patch: Partial<SearchProfile>) => patchProfile(profile.name, patch),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['config'] }),
  })
  const scrapeMutation = useMutation({
    mutationFn: () => triggerScrape({ profile: profile.name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scrape-status'] })
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['runs'] }), 5000)
    },
  })

  return (
    <tr className="border-t border-slate-800">
      <td className="px-3 py-2">
        <input
          type="checkbox"
          checked={profile.enabled}
          disabled={mutation.isPending}
          onChange={(e) => mutation.mutate({ enabled: e.target.checked })}
        />
      </td>
      <td className="px-3 py-2 font-medium">{profile.name}</td>
      <td className="px-3 py-2 text-slate-400 max-w-[14rem] truncate">
        {profile.search_term}
        {profile.location ? ` · ${profile.location}` : ''}
        {profile.is_remote ? ' · remote' : ''}
      </td>
      <td className="px-3 py-2">
        <input
          type="number"
          className="bg-slate-900 border border-slate-700 rounded px-2 py-1 w-24 text-sm"
          defaultValue={profile.interval_minutes}
          min={15}
          onBlur={(e) => {
            const v = Number(e.target.value)
            if (v && v !== profile.interval_minutes)
              mutation.mutate({ interval_minutes: v })
          }}
        />
      </td>
      <td className="px-3 py-2 text-slate-400">{profile.results_wanted}</td>
      <td className="px-3 py-2 text-slate-400">{profile.hours_old ?? '—'}</td>
      <td className="px-3 py-2">
        <button
          className="px-3 py-1 rounded bg-indigo-700 hover:bg-indigo-600 text-sm disabled:opacity-40"
          disabled={scrapeMutation.isPending}
          onClick={() => scrapeMutation.mutate()}
        >
          ▶ Run now
        </button>
      </td>
    </tr>
  )
}

export default function AdminPanel() {
  const queryClient = useQueryClient()
  const { data: config } = useQuery({ queryKey: ['config'], queryFn: fetchConfig })
  const { data: runs } = useQuery({
    queryKey: ['runs'],
    queryFn: fetchRuns,
    refetchInterval: 10_000,
  })
  const { data: scrapeStatus } = useQuery({
    queryKey: ['scrape-status'],
    queryFn: fetchScrapeStatus,
    refetchInterval: 3_000,
  })
  const scrapeAll = useMutation({
    mutationFn: () => triggerScrape({}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scrape-status'] }),
  })

  return (
    <div className="space-y-6">
      <section>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-semibold">Search profiles</h2>
          <div className="flex items-center gap-3">
            {scrapeStatus?.running && (
              <span className="text-sm text-amber-400 animate-pulse">
                ⏳ Scrape running…
              </span>
            )}
            <button
              className="px-3 py-1.5 rounded bg-emerald-700 hover:bg-emerald-600 text-sm disabled:opacity-40"
              disabled={scrapeAll.isPending || scrapeStatus?.running}
              onClick={() => scrapeAll.mutate()}
            >
              ▶ Run all now
            </button>
          </div>
        </div>
        <div className="overflow-x-auto rounded-lg border border-slate-800">
          <table className="w-full text-sm">
            <thead className="bg-slate-900 text-slate-400 text-left">
              <tr>
                {['On', 'Profile', 'Query', 'Every (min)', 'Results', 'Fresh (h)', ''].map((h) => (
                  <th key={h} className="px-3 py-2 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {config?.search_profiles.map((p) => <ProfileRow key={p.name} profile={p} />)}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-slate-500 mt-1">
          Per-source minimum intervals are enforced server-side regardless of this
          setting (anti-ban). Add/remove profiles by editing config.yaml.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold mb-2">Run history</h2>
        <div className="overflow-x-auto rounded-lg border border-slate-800">
          <table className="w-full text-sm">
            <thead className="bg-slate-900 text-slate-400 text-left">
              <tr>
                {['Started', 'Trigger', 'Profile', 'Source', 'Status', 'Found', 'New', 'Removed', 'Error'].map(
                  (h) => (
                    <th key={h} className="px-3 py-2 font-medium">
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {runs?.map((r) => (
                <tr key={r.id} className="border-t border-slate-800">
                  <td className="px-3 py-2 whitespace-nowrap text-slate-400">
                    {new Date(r.started_at).toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-slate-400">{r.trigger}</td>
                  <td className="px-3 py-2">{r.profile_name}</td>
                  <td className="px-3 py-2">{r.source}</td>
                  <td className={`px-3 py-2 ${RUN_STATUS[r.status] ?? ''}`}>{r.status}</td>
                  <td className="px-3 py-2">{r.jobs_found ?? '—'}</td>
                  <td className="px-3 py-2">{r.jobs_new ?? '—'}</td>
                  <td className="px-3 py-2">{r.jobs_removed ?? '—'}</td>
                  <td className="px-3 py-2 text-red-400 max-w-[16rem] truncate">
                    {r.error ?? ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {runs?.length === 0 && (
            <p className="px-4 py-6 text-center text-slate-400">No runs recorded yet.</p>
          )}
        </div>
      </section>
    </div>
  )
}
