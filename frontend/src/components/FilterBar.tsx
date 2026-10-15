import { useQuery } from '@tanstack/react-query'
import { fetchFilterOptions, fetchTags, type JobFilters } from '../api'

interface Props {
  filters: JobFilters
  onChange: (patch: Partial<JobFilters>) => void
}

function Select({
  label,
  value,
  options,
  onSelect,
}: {
  label: string
  value: string
  options: string[]
  onSelect: (v: string) => void
}) {
  return (
    <select
      className="bg-slate-900 border border-slate-700 rounded px-2 py-1.5 text-sm"
      value={value}
      onChange={(e) => onSelect(e.target.value)}
      aria-label={label}
    >
      <option value="">{label}</option>
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  )
}

export default function FilterBar({ filters, onChange }: Props) {
  const { data: options } = useQuery({ queryKey: ['filters'], queryFn: fetchFilterOptions })
  const { data: tags } = useQuery({ queryKey: ['tags'], queryFn: fetchTags })

  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        type="search"
        placeholder="Search title, company, description…"
        className="bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-sm w-64"
        value={filters.q ?? ''}
        onChange={(e) => onChange({ q: e.target.value || undefined })}
      />
      <Select
        label="Source"
        value={filters.source?.[0] ?? ''}
        options={options?.sources ?? []}
        onSelect={(v) => onChange({ source: v ? [v] : undefined })}
      />
      <Select
        label="Seniority"
        value={filters.seniority?.[0] ?? ''}
        options={options?.seniority ?? []}
        onSelect={(v) => onChange({ seniority: v ? [v] : undefined })}
      />
      <Select
        label="Remote type"
        value={filters.remote_type?.[0] ?? ''}
        options={options?.remote_types ?? []}
        onSelect={(v) => onChange({ remote_type: v ? [v] : undefined })}
      />
      <Select
        label="City"
        value={filters.city ?? ''}
        options={options?.cities ?? []}
        onSelect={(v) => onChange({ city: v || undefined })}
      />
      <Select
        label="Tag"
        value={filters.tags?.[0] ?? ''}
        options={Object.keys(tags ?? {})}
        onSelect={(v) => onChange({ tags: v ? [v] : undefined })}
      />
      <input
        type="number"
        placeholder="Min salary €/yr"
        className="bg-slate-900 border border-slate-700 rounded px-2 py-1.5 text-sm w-32"
        value={filters.salary_min ?? ''}
        onChange={(e) =>
          onChange({ salary_min: e.target.value ? Number(e.target.value) : undefined })
        }
      />
      <label className="flex items-center gap-1.5 text-sm text-slate-300">
        <input
          type="checkbox"
          checked={filters.new_only ?? false}
          onChange={(e) => onChange({ new_only: e.target.checked || undefined })}
        />
        🆕 New only
      </label>
      <label className="flex items-center gap-1.5 text-sm text-slate-300">
        <input
          type="checkbox"
          checked={filters.has_salary ?? false}
          onChange={(e) => onChange({ has_salary: e.target.checked || undefined })}
        />
        💰 Has salary
      </label>
      <label className="flex items-center gap-1.5 text-sm text-slate-300">
        <input
          type="checkbox"
          checked={filters.removed ?? false}
          onChange={(e) => onChange({ removed: e.target.checked || undefined })}
        />
        ⚠️ Removed
      </label>
    </div>
  )
}
