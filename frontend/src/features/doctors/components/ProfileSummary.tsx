import { Link } from 'react-router-dom';
import type { DoctorSummary } from '../../../api/contracts';
import { displayValue } from '../../../utils/formatters';

export function ProfileSummary({
  doctor,
  onViewEvidence,
}: {
  doctor: DoctorSummary;
  onViewEvidence?: (hint?: string) => void;
}) {
  const primary = doctor.primary_affiliation;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
        <h3 className="text-sm font-semibold">Identity</h3>
        <dl className="mt-3 space-y-2 text-sm">
          <Row label="Preferred name" value={doctor.preferred_name} />
          <Row label="Previous names" value={doctor.previous_names.join(', ') || 'None recorded'} />
          <Row label="Specialty" value={displayValue(doctor.specialty)} />
          <Row label="Credential" value={displayValue(doctor.credential_details)} />
          <Row
            label="Source coverage"
            value={doctor.source_coverage.map((s) => String(s.source_name)).join(', ') || 'None'}
          />
        </dl>
        <button
          type="button"
          className="mt-3 text-sm font-medium text-primary hover:underline"
          onClick={() => onViewEvidence?.('lineage')}
        >
          View evidence ({doctor.aliases.length || 1})
        </button>
      </section>

      <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm">
        <h3 className="text-sm font-semibold">Contact</h3>
        <dl className="mt-3 space-y-2 text-sm">
          <Row label="Professional email" value={displayValue(doctor.professional_email)} />
          <Row label="Professional phone" value={displayValue(doctor.professional_phone)} />
          <Row label="Official NPI" value={doctor.official_npi ? `${doctor.official_npi} · ${doctor.npi_status}` : 'No NPI on file'} />
        </dl>
      </section>

      <section className="rounded-[12px] border border-border bg-white p-4 shadow-sm lg:col-span-2">
        <h3 className="text-sm font-semibold">Affiliations</h3>
        <ul className="mt-3 space-y-2">
          {doctor.affiliations.map((aff) => (
            <li key={String(aff.affiliation_id)} className="rounded-md border border-border px-3 py-2 text-sm">
              <div className="font-medium">{String(aff.organization_name)}</div>
              <div className="text-muted">
                {displayValue(aff.city)}, {displayValue(aff.state)} · {String(aff.relationship_status)}
                {aff.is_primary ? ' · Primary' : ''}
                {aff.effective_from ? ` · Effective ${String(aff.effective_from)}` : ' · Effective date unknown'}
              </div>
            </li>
          ))}
        </ul>
        {primary ? (
          <p className="mt-2 text-xs text-muted">
            Current known/selected affiliation: {String(primary.organization_name)}
          </p>
        ) : null}
      </section>

      {doctor.pending_updates.length ? (
        <section className="rounded-[12px] border border-amber-200 bg-amber-50 p-4 lg:col-span-2">
          <h3 className="text-sm font-semibold text-amber-950">Pending updates</h3>
          <div className="mt-3 space-y-3">
            {doctor.pending_updates.map((u) => (
              <div key={String(u.review_id)} className="rounded-md border border-amber-200 bg-white p-3 text-sm">
                <div className="grid gap-2 md:grid-cols-3">
                  <div>
                    <div className="text-xs text-muted">Before</div>
                    <div>{displayValue(u.before_value)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted">Proposed</div>
                    <div className="font-medium">{displayValue(u.proposed_value)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted">Evidence</div>
                    <div>{displayValue(u.evidence_hint, 'See review')}</div>
                  </div>
                </div>
                <Link
                  to={`/review/${String(u.review_id)}`}
                  className="mt-2 inline-block text-sm font-medium text-primary hover:underline"
                >
                  Open review
                </Link>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right font-medium text-foreground">{value}</dd>
    </div>
  );
}
