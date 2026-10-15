import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { checkClosed, fetchCriteria, patchCriteria, type Criteria } from '../api'

const field = 'w-full rounded-md bg-slate-900 px-3 py-2 text-sm ring-1 ring-slate-700 focus:outline-none focus:ring-indigo-500'

function ListField({ label, hint, value, onChange }: { label: string; hint: string; value: string[]; onChange: (v: string[]) => void }) {
  const [text, setText] = useState(value.join(', '))
  useEffect(() => setText(value.join(', ')), [value])
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium text-slate-200">{label}</span>
      <span className="block text-xs text-slate-500">{hint}</span>
      <textarea
        className={`${field} h-20`}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => onChange(text.split(',').map((s) => s.trim()).filter(Boolean))}
      />
    </label>
  )
}

/** Edits the criteria that decide which postings are kept and how they are scored. */
export default function CriteriaEditor() {
  const queryClient = useQueryClient()
  const { data } = useQuery({ queryKey: ['criteria'], queryFn: fetchCriteria })
  const [draft, setDraft] = useState<Criteria | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  useEffect(() => setDraft(data ?? null), [data])

  const save = useMutation({
    mutationFn: (c: Criteria) => patchCriteria(c),
    onSuccess: (c) => {
      queryClient.setQueryData(['criteria'], c)
      setMessage('Saved. New searches use these criteria.')
    },
    onError: (e: Error) => setMessage(`Not saved: ${e.message}`),
  })
  const sweep = useMutation({
    mutationFn: checkClosed,
    onSuccess: (r) => {
      setMessage(`${r.closed} position${r.closed === 1 ? '' : 's'} closed.`)
      for (const key of ['jobs', 'views', 'stats']) queryClient.invalidateQueries({ queryKey: [key] })
    },
  })

  if (!draft) return <p className="text-slate-400">Loading…</p>
  const set = (patch: Partial<Criteria>) => setDraft({ ...draft, ...patch })

  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <h1 className="text-xl font-semibold">Search criteria</h1>
        <p className="mt-1 text-sm text-slate-400">
          Every board result is checked against these rules. Postings that fail are not stored; the ones that pass get a
          fit score from 0 to 100.
        </p>
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        <label className="block space-y-1">
          <span className="text-sm font-medium text-slate-200">Minimum salary (EUR per year)</span>
          <span className="block text-xs text-slate-500">Other currencies, monthly and hourly pay are converted.</span>
          <input
            type="number"
            className={field}
            value={draft.min_salary_eur ?? ''}
            onChange={(e) => set({ min_salary_eur: e.target.value ? Number(e.target.value) : null })}
          />
        </label>
        <div className="space-y-2">
          <span className="text-sm font-medium text-slate-200">Seniority</span>
          <div className="flex flex-wrap gap-3 pt-1">
            {['junior', 'mid', 'senior', 'lead'].map((s) => (
              <label key={s} className="flex items-center gap-1.5 text-sm text-slate-300">
                <input
                  type="checkbox"
                  className="accent-indigo-500"
                  checked={draft.seniority.includes(s)}
                  onChange={() =>
                    set({ seniority: draft.seniority.includes(s) ? draft.seniority.filter((x) => x !== s) : [...draft.seniority, s] })
                  }
                />
                {s}
              </label>
            ))}
          </div>
          <label className="flex items-center gap-1.5 text-sm text-slate-300">
            <input
              type="checkbox"
              className="accent-indigo-500"
              checked={draft.keep_unknown_salary}
              onChange={(e) => set({ keep_unknown_salary: e.target.checked })}
            />
            Keep postings that don't state a salary
          </label>
        </div>
      </div>

      <ListField
        label="Cities for hybrid or on-site work"
        hint="Outside these, only remote positions are kept."
        value={draft.location.hybrid_cities}
        onChange={(v) => set({ location: { ...draft.location, hybrid_cities: v } })}
      />
      <ListField
        label="Regions a remote job must be open to"
        hint="A remote job restricted to other regions (for example US only) is dropped."
        value={draft.location.remote_allowed_regions}
        onChange={(v) => set({ location: { ...draft.location, remote_allowed_regions: v } })}
      />
      <ListField
        label="Role keywords"
        hint="The title or tags must contain one of these."
        value={draft.role_keywords}
        onChange={(v) => set({ role_keywords: v })}
      />
      <ListField
        label="Excluded title words"
        hint="Titles containing any of these are dropped."
        value={draft.exclude_title_keywords}
        onChange={(v) => set({ exclude_title_keywords: v })}
      />
      <ListField
        label="Preferred skills"
        hint="Raise the fit score when they appear in the title, tags or description."
        value={draft.boost_keywords}
        onChange={(v) => set({ boost_keywords: v })}
      />

      <div className="flex items-center gap-3 border-t border-slate-800 pt-5">
        <button
          onClick={() => save.mutate(draft)}
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50"
          disabled={save.isPending}
        >
          Save criteria
        </button>
        <button
          onClick={() => sweep.mutate()}
          className="rounded-md bg-slate-800 px-4 py-2 text-sm hover:bg-slate-700 disabled:opacity-50"
          disabled={sweep.isPending}
          title="Close expired and stale positions and re-check the ones in your pipeline"
        >
          {sweep.isPending ? 'Checking…' : 'Check for closed positions now'}
        </button>
        {message && <span className="text-sm text-slate-400">{message}</span>}
      </div>
    </div>
  )
}
