import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteProfile,
  fetchConfig,
  fetchRuns,
  fetchScrapeStatus,
  patchProfile,
  triggerScrape,
  type SearchProfile,
} from '../api'
import SourcesPanel from './SourcesPanel'
import TimelineChart from './TimelineChart'
import ProfileEditor from './ProfileEditor'

const RUN_STATUS: Record<string, string> = {
  ok: 'text-emerald-400',
  failed: 'text-red-400',
  skipped_rate_limit: 'text-sky-400',
}

function ProfileRow({
  profile,
  onEdit,
}: {
  profile: SearchProfile
  onEdit: () => void
}) {
  const queryClient = useQueryClient()
  const toggle = useMutation({
    mutationFn: () => patchProfile(profile.name, { enabled: !profile.enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['config'] }),
  })
  const remove = useMutation({
    mutationFn: () => deleteProfile(profile.name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['config'] }),
  })
  const scrape = useMutation({
    mutationFn: () => triggerScrape({ profile: profile.name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scrape-status'] })
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['runs'] }), 5000)
    },
  })

  return (
    <tr className={`border-t border-slate-800 ${profile.enabled ? '' : 'opacity-50'}`}>
      <td className="px-3 py-2">
        <input
          type="checkbox"
          checked={profile.enabled}
          disabled={toggle.isPending}
          onChange={() => toggle.mutate()}
        />
      </td>
      <td className="px-3 py-2 font-medium">{profile.name}</td>
      <td className="px-3 py-2 text-slate-400 max-w-[14rem] truncate" title={profile.search_term}>
        {profile.search_term}
        {profile.location ? ` · ${profile.location}` : ''}
        {profile.is_remote === true ? ' · remote' : profile.is_remote === false ? ' · on-site' : ''}
      </td>
      <td className="px-3 py-2">
        <div className="flex flex-wrap gap-1 max-w-[12rem]">
          {profile.tags.map((t) => (
            <span key={t} className="px-1.5 py-0.5 rounded bg-slate-800 text-xs">
              {t}
            </span>
          ))}
        </div>
      </td>
      <td className="px-3 py-2 text-slate-400">{profile.runs_per_day}×/day</td>
      <td className="px-3 py-2 text-slate-400">{profile.results_wanted}</td>
      <td className="px-3 py-2 text-slate-400">{profile.hours_old ?? '—'}h</td>
      <td className="px-3 py-2 whitespace-nowrap">
        <button
          className="px-2 py-1 rounded bg-indigo-700 hover:bg-indigo-600 text-xs disabled:opacity-40"
          disabled={scrape.isPending}
          onClick={() => scrape.mutate()}
        >
          ▶ Run
        </button>{' '}
        <button
          className="px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 text-xs"
          onClick={onEdit}
        >
          ✏️ Edit
        </button>{' '}
        <button
          className="px-2 py-1 rounded bg-red-900 hover:bg-red-800 text-xs disabled:opacity-40"
          disabled={remove.isPending}
          onClick={() => {
            if (confirm(`Delete profile "${profile.name}"? (tracked jobs are kept)`))
              remove.mutate()
          }}
        >
          🗑
        </button>
      </td>
    </tr>
  )
}

export default function AdminPanel() {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState<SearchProfile | null>(null)
  const [creating, setCreating] = useState(false)
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
      <SourcesPanel />
      <TimelineChart />

      <section>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-semibold">Search profiles</h2>
          <div className="flex items-center gap-3">
            {scrapeStatus?.running && (
              <span className="text-sm text-amber-400 animate-pulse">⏳ Scrape running…</span>
            )}
            <button
              className="px-3 py-1.5 rounded bg-slate-700 hover:bg-slate-600 text-sm"
              onClick={() => setCreating(true)}
            >
              ➕ New profile
            </button>
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
                {['On', 'Profile', 'Query', 'Tags', 'Freq', 'Results', 'Fresh', ''].map((h) => (
                  <th key={h} className="px-3 py-2 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {config?.search_profiles.map((p) => (
                <ProfileRow key={p.name} profile={p} onEdit={() => setEditing(p)} />
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-slate-500 mt-1">
          Per-source minimum intervals are enforced server-side regardless of these
          settings (anti-ban). Deleting a profile keeps its already-tracked jobs.
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
                  <td className="px-3 py-2 text-red-400 max-w-[16rem] truncate" title={r.error ?? ''}>
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

      {editing && <ProfileEditor profile={editing} onClose={() => setEditing(null)} />}
      {creating && <ProfileEditor profile={null} onClose={() => setCreating(false)} />}
    </div>
  )
}
