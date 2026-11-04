import { displayValue } from '../../../utils/formatters';

export function ReviewComparison({ comparison }: { comparison: Record<string, unknown> }) {
  const source = (comparison.source_profile || {}) as Record<string, unknown>;
  const doctor = (comparison.doctor_profile || {}) as Record<string, unknown>;
  const agreements = (comparison.agreements || []) as Array<Record<string, unknown>>;
  const conflicts = (comparison.conflicts || []) as Array<Record<string, unknown>>;

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        <ProfileCard title="Source record" rows={[
          ['Name', source.recorded_name],
          ['Specialty', source.specialty],
          ['Practice', source.practice_name],
          ['Email', source.email],
          ['Credential', source.credential_reference],
          ['State', source.state],
        ]} />
        <ProfileCard title="Golden / candidate profile" rows={[
          ['Name', doctor.preferred_name],
          ['Specialty', doctor.specialty],
          ['Email', doctor.email],
          ['City', doctor.city],
          ['State', doctor.state],
          ['Doctor ID', doctor.doctor_id],
        ]} />
      </div>
      <div className="grid gap-3 md:grid-cols-2 text-sm">
        <div className="rounded-[12px] border border-emerald-200 bg-emerald-50 p-3">
          <h4 className="font-semibold text-emerald-950">Agreements</h4>
          <ul className="mt-2 space-y-1">
            {agreements.length ? agreements.map((a, i) => (
              <li key={i}>{displayValue(a.field)}: {displayValue(a.value)}</li>
            )) : <li>None highlighted</li>}
          </ul>
        </div>
        <div className="rounded-[12px] border border-rose-200 bg-rose-50 p-3">
          <h4 className="font-semibold text-rose-950">Conflicts</h4>
          <ul className="mt-2 space-y-1">
            {conflicts.length ? conflicts.map((c, i) => (
              <li key={i}>{displayValue(c.field)}: {displayValue(c.source)} vs {displayValue(c.doctor)}</li>
            )) : <li>None highlighted</li>}
          </ul>
        </div>
      </div>
    </div>
  );
}

function ProfileCard({ title, rows }: { title: string; rows: Array<[string, unknown]> }) {
  return (
    <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold">{title}</h3>
      <dl className="mt-3 space-y-1 text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-3">
            <dt className="text-muted">{label}</dt>
            <dd>{displayValue(value)}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
