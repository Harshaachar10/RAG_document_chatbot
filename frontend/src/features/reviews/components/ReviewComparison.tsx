import { displayValue } from '../../../utils/formatters';

type Assessment = {
  field?: string;
  label?: string;
  status?: string;
  source_value?: unknown;
  doctor_value?: unknown;
  explanation?: string;
};

type ConflictFocus = {
  kind?: string;
  label?: string;
  supplied_identifier?: string | null;
  identifier_kind?: string | null;
  golden_identifier?: string | null;
  candidate_identifier?: string | null;
  candidate_doctor_id?: string | null;
  candidate_name?: string | null;
  explanation?: string;
  evidence_ids?: string[];
};

const STATUS_STYLES: Record<string, string> = {
  match: 'border-emerald-200 bg-emerald-50 text-emerald-950',
  conflict: 'border-rose-200 bg-rose-50 text-rose-950',
  missing: 'border-amber-200 bg-amber-50 text-amber-950',
  uncertain: 'border-slate-200 bg-slate-50 text-slate-800',
};

const STATUS_LABELS: Record<string, string> = {
  match: 'Matches',
  conflict: 'Conflicts',
  missing: 'Missing',
  uncertain: 'Uncertain',
};

export function ReviewComparison({
  comparison,
  caseTitle,
  doctorId,
  onOpenEvidence,
}: {
  comparison: Record<string, unknown>;
  caseTitle?: string;
  doctorId?: string | null;
  onOpenEvidence?: (evidenceId: string) => void;
}) {
  const source = (comparison.source_profile || {}) as Record<string, unknown>;
  const doctor = (comparison.doctor_profile || {}) as Record<string, unknown>;
  const candidate = (comparison.candidate_profile || null) as Record<string, unknown> | null;
  const assessments = (comparison.field_assessments || []) as Assessment[];
  const focus = (comparison.conflict_focus || null) as ConflictFocus | null;
  const summary = (comparison.submission_summary || {}) as {
    provided?: string[];
    missing?: string[];
    conflicts?: string[];
    uncertain?: string[];
  };

  return (
    <div className="space-y-4">
      <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
        <h3 className="text-sm font-semibold">Case identity</h3>
        <p className="mt-1 text-sm text-muted">{displayValue(caseTitle, 'Selected review case')}</p>
        <dl className="mt-3 grid gap-2 text-sm md:grid-cols-3">
          <div>
            <dt className="text-muted">Doctor</dt>
            <dd className="font-medium">{displayValue(doctor.preferred_name)}</dd>
            <dd className="text-xs text-muted">{displayValue(doctor.doctor_id || doctorId)}</dd>
          </div>
          <div>
            <dt className="text-muted">Golden NPI reference</dt>
            <dd className="font-medium">{displayValue(doctor.npi_display, 'Not recorded')}</dd>
          </div>
          <div>
            <dt className="text-muted">Source record</dt>
            <dd className="font-medium">{displayValue(source.source_record_id)}</dd>
            <dd className="text-xs text-muted">{displayValue(source.recorded_name)}</dd>
          </div>
        </dl>
      </section>

      {focus ? (
        <section className="rounded-[12px] border border-rose-200 bg-rose-50 p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-rose-950">{displayValue(focus.label, 'Identifier conflict')}</h3>
          <p className="mt-2 text-sm text-rose-900">{displayValue(focus.explanation)}</p>
          <dl className="mt-3 grid gap-3 text-sm md:grid-cols-3">
            <div className="rounded-md border border-rose-200 bg-white p-3">
              <dt className="text-xs uppercase tracking-wide text-muted">Supplied on this document</dt>
              <dd className="mt-1 font-semibold">{displayValue(focus.supplied_identifier, 'Not provided')}</dd>
              <dd className="mt-1 text-xs text-muted">Kind: {displayValue(focus.identifier_kind, '—')}</dd>
            </div>
            <div className="rounded-md border border-rose-200 bg-white p-3">
              <dt className="text-xs uppercase tracking-wide text-muted">Golden / expected reference</dt>
              <dd className="mt-1 font-semibold">{displayValue(focus.golden_identifier, 'Not recorded')}</dd>
            </div>
            <div className="rounded-md border border-rose-200 bg-white p-3">
              <dt className="text-xs uppercase tracking-wide text-muted">Conflicting candidate</dt>
              <dd className="mt-1 font-semibold">{displayValue(focus.candidate_name || candidate?.preferred_name, 'Same master profile')}</dd>
              <dd className="mt-1 text-xs text-muted">
                {displayValue(focus.candidate_doctor_id || candidate?.doctor_id, displayValue(doctor.doctor_id))}
                {focus.candidate_identifier ? ` · ${focus.candidate_identifier}` : ''}
              </dd>
            </div>
          </dl>
          {(focus.evidence_ids || []).length ? (
            <div className="mt-3 flex flex-wrap gap-2 text-sm">
              {(focus.evidence_ids || []).map((id) => (
                <button
                  key={id}
                  type="button"
                  className="rounded-md border border-rose-300 bg-white px-2.5 py-1 text-rose-950 hover:bg-rose-100"
                  onClick={() => onOpenEvidence?.(id)}
                >
                  Open evidence {id}
                </button>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2">
        <ProfileCard
          title="What this submission provided"
          rows={[
            ['Name', source.recorded_name],
            ['NPI / identifier', source.npi_display || source.provider_identifier],
            ['Identifier kind', source.identifier_kind],
            ['Specialty', source.specialty],
            ['Practice', source.practice_name],
            ['Address', source.address_line],
            ['Email', source.email],
            ['Credential', source.credential_reference],
          ]}
        />
        <ProfileCard
          title="Golden / candidate profile"
          rows={[
            ['Name', doctor.preferred_name],
            ['Doctor ID', doctor.doctor_id],
            ['NPI reference', doctor.npi_display],
            ['Specialty', doctor.specialty],
            ['Email', doctor.email],
            ['City', doctor.city],
            ['State', doctor.state],
          ]}
        />
      </div>

      <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
        <h3 className="text-sm font-semibold">Field-by-field assessment</h3>
        <p className="mt-1 text-xs text-muted">
          Labels reflect only what appears on the selected submission and golden profile — nothing is invented to fit the case title.
        </p>
        <div className="mt-3 space-y-2">
          {assessments.map((row) => {
            const status = row.status || 'uncertain';
            return (
              <div key={`${row.field}-${status}`} className={`rounded-md border px-3 py-2 text-sm ${STATUS_STYLES[status] || STATUS_STYLES.uncertain}`}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium">{displayValue(row.label || row.field)}</span>
                  <span className="rounded bg-white/70 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide">
                    {STATUS_LABELS[status] || status}
                  </span>
                </div>
                <div className="mt-1 grid gap-1 md:grid-cols-2">
                  <div>Submission: {displayValue(row.source_value, 'Not provided')}</div>
                  <div>Golden: {displayValue(row.doctor_value, 'Not recorded')}</div>
                </div>
                <p className="mt-1 text-xs opacity-90">{displayValue(row.explanation)}</p>
              </div>
            );
          })}
          {!assessments.length ? <p className="text-sm text-muted">No comparable fields were available for this case.</p> : null}
        </div>
      </section>

      <div className="grid gap-3 md:grid-cols-4 text-sm">
        <SummaryChip title="Provided" items={summary.provided || []} tone="emerald" />
        <SummaryChip title="Missing" items={summary.missing || []} tone="amber" />
        <SummaryChip title="Conflicts" items={summary.conflicts || []} tone="rose" />
        <SummaryChip title="Uncertain" items={summary.uncertain || []} tone="slate" />
      </div>
    </div>
  );
}

function SummaryChip({
  title,
  items,
  tone,
}: {
  title: string;
  items: string[];
  tone: 'emerald' | 'amber' | 'rose' | 'slate';
}) {
  const tones = {
    emerald: 'border-emerald-200 bg-emerald-50 text-emerald-950',
    amber: 'border-amber-200 bg-amber-50 text-amber-950',
    rose: 'border-rose-200 bg-rose-50 text-rose-950',
    slate: 'border-slate-200 bg-slate-50 text-slate-800',
  };
  return (
    <div className={`rounded-[12px] border p-3 ${tones[tone]}`}>
      <h4 className="font-semibold">{title}</h4>
      <ul className="mt-2 space-y-1">
        {items.length ? items.map((item) => <li key={item}>{item}</li>) : <li>None</li>}
      </ul>
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
            <dd className="text-right">{displayValue(value)}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
