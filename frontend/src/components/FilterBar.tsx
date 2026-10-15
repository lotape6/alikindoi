import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchCriteria, fetchFilterOptions, fetchTags, type JobFilters } from '../api'
import { sourceLabel } from '../format'

interface Props {
  filters: JobFilters
  onChange: (patch: Partial<JobFilters>) => void
  onReset: () => void
  total?: number
}

const SORTS: { value: string; label: string }[] = [
  { value: 'fit_score:desc', label: 'Best fit' },
  { value: 'first_seen_at:desc', label: 'Newest found' },
  { value: 'date_posted:desc', label: 'Newest posted' },
  { value: 'salary_annual_max:desc', label: 'Highest salary' },
  { value: 'next_action_at:asc', label: 'Follow-up date' },
  { value: 'company:asc', label: 'Company A–Z' },
  { value: 'closed_at:desc', label: 'Recently closed' },
]

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full px-3 py-1 text-xs ring-1 transition ${
        active
          ? 'bg-indigo-500/20 text-indigo-200 ring-indigo-400/50'
          : 'bg-slate-900 text-slate-300 ring-slate-700 hover:ring-slate-500'
      }`}
    >
      {children}
    </button>
  )
}

/** Compact multi-select: a button that opens a checklist. */
function MultiSelect({
  label, options, selected, onChange, format = (v) => v,
}: {
  label: string
  options: string[]
  selected: string[]
  onChange: (v: string[]) => void
  format?: (v: string) => string
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  const toggle = (v: string) =>
    onChange(selected.includes(v) ? selected.filter((x) => x !== v) : [...selected, v])
  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className={`rounded-md px-3 py-1.5 text-sm ring-1 ${
          selected.length ? 'ring-indigo-400/60 text-indigo-200 bg-indigo-500/10' : 'ring-slate-700 text-slate-300 bg-slate-900'
        }`}
      >
        {label}
        {selected.length > 0 && <span className="ml-1.5 text-xs">({selected.length})</span>}
        <span className="ml-1.5 text-slate-500">▾</span>
      </button>
      {open && (
        <div className="absolute z-30 mt-1 max-h-72 w-56 overflow-y-auto rounded-md bg-slate-900 p-1 shadow-xl ring-1 ring-slate-700">
          {options.length === 0 && <p className="px-2 py-1.5 text-xs text-slate-500">No options yet</p>}
          {options.map((o) => (
            <label key={o} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-slate-800">
              <input type="checkbox" checked={selected.includes(o)} onChange={() => toggle(o)} className="accent-indigo-500" />
              {format(o)}
            </label>
          ))}
        </div>
      )}
    </div>
  )
}

const fold = (s: string) => s.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()

/** One chip per city: 'malaga' and 'málaga' collapse (accented spelling wins),
 * and the English 'seville' is dropped when 'sevilla' is configured. */
function cityChips(cities: string[]): string[] {
  const byKey = new Map<string, string>()
  for (const c of cities) {
    const key = fold(c)
    if (!byKey.has(key) || c !== key) byKey.set(key, c)
  }
  if (byKey.has('sevilla')) byKey.delete('seville')
  return [...byKey.values()]
}

export default function FilterBar({ filters, onChange, onReset, total }: Props) {
  const { data: options } = useQuery({ queryKey: ['filters'], queryFn: fetchFilterOptions })
  const { data: tags } = useQuery({ queryKey: ['tags'], queryFn: fetchTags })
  const { data: criteria } = useQuery({ queryKey: ['criteria'], queryFn: fetchCriteria })
  const [q, setQ] = useState(filters.q ?? '')

  // Debounce typing so the list does not refetch on every keystroke.
  useEffect(() => setQ(filters.q ?? ''), [filters.q])
  useEffect(() => {
    const t = setTimeout(() => {
      if ((filters.q ?? '') !== q) onChange({ q: q || undefined })
    }, 300)
    return () => clearTimeout(t)
  }, [q]) // eslint-disable-line react-hooks/exhaustive-deps

  const remote = filters.remote_type ?? []
  const minSalary = criteria?.min_salary_eur ?? 48000
  const sort = `${filters.sort_by ?? 'fit_score'}:${filters.sort_dir ?? 'desc'}`
  const active =
    !!filters.q || !!filters.tags?.length || !!filters.source?.length || !!filters.seniority?.length ||
    !!remote.length || !!filters.city || !!filters.salary_min || !!filters.fit_min || !!filters.has_salary

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-64 max-w-xl">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500">⌕</span>
          <input
            id="job-search"
            type="search"
            placeholder="Search role, company, location, notes…   ( / )"
            className="w-full rounded-md bg-slate-900 py-1.5 pl-8 pr-3 text-sm ring-1 ring-slate-700 focus:outline-none focus:ring-indigo-500"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <MultiSelect
          label="Board"
          options={options?.sources ?? []}
          selected={filters.source ?? []}
          onChange={(v) => onChange({ source: v.length ? v : undefined })}
          format={sourceLabel}
        />
        <MultiSelect
          label="Seniority"
          options={options?.seniority ?? []}
          selected={filters.seniority ?? []}
          onChange={(v) => onChange({ seniority: v.length ? v : undefined })}
        />
        <MultiSelect
          label="Skills"
          options={Object.keys(tags ?? {}).slice(0, 60)}
          selected={filters.tags ?? []}
          onChange={(v) => onChange({ tags: v.length ? v : undefined })}
        />
        <select
          aria-label="Sort"
          className="rounded-md bg-slate-900 px-2 py-1.5 text-sm ring-1 ring-slate-700"
          value={sort}
          onChange={(e) => {
            const [sort_by, sort_dir] = e.target.value.split(':')
            onChange({ sort_by, sort_dir: sort_dir as 'asc' | 'desc' })
          }}
        >
          {SORTS.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Chip
          active={remote.length === 1 && remote[0] === 'remote'}
          onClick={() => onChange({ remote_type: remote[0] === 'remote' && remote.length === 1 ? undefined : ['remote'] })}
        >
          Remote
        </Chip>
        <Chip
          active={remote.includes('hybrid') && remote.includes('onsite')}
          onClick={() =>
            onChange({ remote_type: remote.includes('hybrid') ? undefined : ['hybrid', 'onsite'] })
          }
        >
          Hybrid / on-site
        </Chip>
        {cityChips(criteria?.location.hybrid_cities ?? ['málaga', 'sevilla']).map((city) => (
          <Chip
            key={city}
            active={filters.city === city}
            onClick={() => onChange({ city: filters.city === city ? undefined : city })}
          >
            {city.charAt(0).toUpperCase() + city.slice(1)}
          </Chip>
        ))}
        <Chip
          active={filters.salary_min === minSalary}
          onClick={() => onChange({ salary_min: filters.salary_min === minSalary ? undefined : minSalary })}
        >
          Salary ≥ {Math.round(minSalary / 1000)}k €
        </Chip>
        <Chip active={!!filters.has_salary} onClick={() => onChange({ has_salary: !filters.has_salary || undefined })}>
          Salary stated
        </Chip>
        <Chip active={filters.fit_min === 70} onClick={() => onChange({ fit_min: filters.fit_min === 70 ? undefined : 70 })}>
          Strong fit
        </Chip>
        {active && (
          <button onClick={onReset} className="text-xs text-slate-400 underline-offset-2 hover:text-slate-200 hover:underline">
            Clear filters
          </button>
        )}
        {total !== undefined && <span className="ml-auto text-xs text-slate-500">{total} position{total === 1 ? '' : 's'}</span>}
      </div>
    </div>
  )
}
