import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createProfile, patchProfile, type SearchProfile } from '../api'

const EMPTY: Partial<SearchProfile> = {
  name: '',
  enabled: true,
  search_term: '',
  google_search_term: '',
  location: '',
  country_indeed: 'Spain',
  adzuna_country: 'es',
  is_remote: null,
  job_type: null,
  tags: [],
  results_wanted: 25,
  hours_old: 72,
  interval_minutes: 360,
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs text-slate-400 uppercase tracking-wide">{label}</span>
      {children}
    </label>
  )
}

const inputCls =
  'mt-1 w-full bg-slate-900 border border-slate-700 rounded px-2 py-1.5 text-sm'

export default function ProfileEditor({
  profile,
  onClose,
}: {
  profile: SearchProfile | null // null = create new
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<Partial<SearchProfile>>(
    profile ? { ...profile } : { ...EMPTY },
  )
  const [tagInput, setTagInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const isNew = profile === null

  const save = useMutation({
    mutationFn: () =>
      isNew
        ? createProfile(form)
        : patchProfile(profile.name, {
            ...form,
            is_remote: form.is_remote,
            job_type: form.job_type,
            google_search_term: form.google_search_term || undefined,
          }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] })
      onClose()
    },
    onError: (e) => setError((e as Error).message),
  })

  const set = <K extends keyof SearchProfile>(key: K, value: SearchProfile[K]) =>
    setForm((f) => ({ ...f, [key]: value }))

  const addTag = () => {
    const tag = tagInput.trim().toLowerCase()
    if (tag && !(form.tags ?? []).includes(tag)) {
      set('tags', [...(form.tags ?? []), tag])
    }
    setTagInput('')
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="w-full max-w-2xl max-h-[90vh] overflow-y-auto bg-slate-950 border border-slate-700 rounded-lg p-6 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold">
          {isNew ? 'New search profile' : `Edit: ${profile.name}`}
        </h2>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Name (unique)">
            <input
              className={inputCls}
              value={form.name ?? ''}
              disabled={!isNew}
              onChange={(e) => set('name', e.target.value)}
              placeholder="python-developer"
            />
          </Field>
          <Field label="Search term">
            <input
              className={inputCls}
              value={form.search_term ?? ''}
              onChange={(e) => set('search_term', e.target.value)}
              placeholder='"c++" developer'
            />
          </Field>
          <Field label="Google Jobs query (optional)">
            <input
              className={inputCls}
              value={form.google_search_term ?? ''}
              onChange={(e) => set('google_search_term', e.target.value)}
              placeholder="c++ developer jobs remote Spain"
            />
          </Field>
          <Field label="Location">
            <input
              className={inputCls}
              value={form.location ?? ''}
              onChange={(e) => set('location', e.target.value)}
              placeholder="Málaga, Spain"
            />
          </Field>
          <Field label="Workplace">
            <select
              className={inputCls}
              value={form.is_remote === null || form.is_remote === undefined ? '' : String(form.is_remote)}
              onChange={(e) =>
                set('is_remote', e.target.value === '' ? null : e.target.value === 'true')
              }
            >
              <option value="">Any (remote + on-site)</option>
              <option value="true">Remote only</option>
              <option value="false">On-site / hybrid only</option>
            </select>
          </Field>
          <Field label="Job type">
            <select
              className={inputCls}
              value={form.job_type ?? ''}
              onChange={(e) => set('job_type', e.target.value || null)}
            >
              <option value="">Any</option>
              <option value="fulltime">Full-time</option>
              <option value="parttime">Part-time</option>
              <option value="contract">Contract</option>
              <option value="internship">Internship</option>
            </select>
          </Field>
          <Field label="Indeed country">
            <input
              className={inputCls}
              value={form.country_indeed ?? 'Spain'}
              onChange={(e) => set('country_indeed', e.target.value)}
            />
          </Field>
          <Field label="Adzuna country code">
            <input
              className={inputCls}
              value={form.adzuna_country ?? 'es'}
              onChange={(e) => set('adzuna_country', e.target.value)}
            />
          </Field>
          <Field label="Results per source (max 100)">
            <input
              type="number"
              className={inputCls}
              value={form.results_wanted ?? 25}
              min={1}
              max={100}
              onChange={(e) => set('results_wanted', Number(e.target.value))}
            />
          </Field>
          <Field label="Freshness (hours old)">
            <input
              type="number"
              className={inputCls}
              value={form.hours_old ?? ''}
              min={1}
              onChange={(e) =>
                set('hours_old', e.target.value ? Number(e.target.value) : null)
              }
            />
          </Field>
          <Field label="Run every (minutes)">
            <input
              type="number"
              className={inputCls}
              value={form.interval_minutes ?? 360}
              min={15}
              onChange={(e) => set('interval_minutes', Number(e.target.value))}
            />
          </Field>
          <Field label="Enabled">
            <div className="mt-2">
              <input
                type="checkbox"
                checked={form.enabled ?? true}
                onChange={(e) => set('enabled', e.target.checked)}
              />
            </div>
          </Field>
        </div>

        <div>
          <span className="text-xs text-slate-400 uppercase tracking-wide">Tags</span>
          <div className="flex flex-wrap gap-2 mt-1 items-center">
            {(form.tags ?? []).map((t) => (
              <span key={t} className="px-2 py-0.5 rounded-full bg-slate-800 text-xs flex items-center gap-1">
                {t}
                <button
                  className="text-slate-400 hover:text-red-400"
                  onClick={() => set('tags', (form.tags ?? []).filter((x) => x !== t))}
                >
                  ✕
                </button>
              </span>
            ))}
            <input
              className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs w-28"
              value={tagInput}
              placeholder="add tag…"
              onChange={(e) => setTagInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addTag())}
              onBlur={addTag}
            />
          </div>
        </div>

        {error && <p className="text-red-400 text-sm">{error}</p>}

        <div className="flex justify-end gap-2">
          <button className="px-4 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-sm" onClick={onClose}>
            Cancel
          </button>
          <button
            className="px-4 py-1.5 rounded bg-indigo-700 hover:bg-indigo-600 text-sm disabled:opacity-40"
            disabled={save.isPending || !form.name || !form.search_term}
            onClick={() => save.mutate()}
          >
            {save.isPending ? 'Saving…' : isNew ? 'Create profile' : 'Save changes'}
          </button>
        </div>
      </div>
    </div>
  )
}
