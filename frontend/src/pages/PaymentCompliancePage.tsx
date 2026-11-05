import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { fetchPaymentCompliance } from '../api/payments';
import { DataTable } from '../components/DataTable';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { FilterBar, FilterField, inputClass } from '../components/FilterBar';
import { TableSkeleton } from '../components/Skeleton';
import { StatusBadge } from '../components/StatusBadge';
import { useUrlState } from '../hooks/useUrlState';
import { displayValue } from '../utils/formatters';

export function PaymentCompliancePage() {
  const { get, setMany } = useUrlState();
  const status = get('status', 'pending');
  const search = get('search');
  const page = Number(get('page', '1'));
  const query = useQuery({
    queryKey: ['payment-compliance', status, search, page],
    queryFn: ({ signal }) => fetchPaymentCompliance({ status, search, page, page_size: 25 }, signal),
  });

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Payment Compliance</h1>
        <p className="mt-1 text-sm text-muted">
          {query.data?.policy || 'Filed and reportable payment values are never changed automatically. Compliance must approve corrections.'}
        </p>
      </header>
      <FilterBar>
        <FilterField label="Search">
          <input className={inputClass} value={search} onChange={(e) => setMany({ search: e.target.value, page: '1' })} />
        </FilterField>
        <FilterField label="Status">
          <select className={inputClass} value={status} onChange={(e) => setMany({ status: e.target.value, page: '1' })}>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="deferred">Deferred</option>
            <option value="">All</option>
          </select>
        </FilterField>
      </FilterBar>
      {query.isLoading ? <TableSkeleton /> : null}
      {query.isError ? <ErrorState message={(query.error as Error).message} onRetry={() => query.refetch()} /> : null}
      {query.data ? (
        <DataTable
          rows={query.data.items}
          rowKey={(r) => String(r.review_id)}
          empty={<EmptyState title="No payment compliance cases" />}
          columns={[
            { key: 'npi', header: 'Stated NPI', render: (r) => displayValue(r.stated_npi) },
            { key: 'recipient', header: 'Recipient', render: (r) => displayValue(r.recipient_name) },
            { key: 'proposed', header: 'Proposed doctor', render: (r) => displayValue(r.proposed_doctor_name, '—') },
            { key: 'reason', header: 'Reason', render: (r) => displayValue(r.reason) },
            { key: 'amount', header: 'Amount', render: (r) => displayValue(r.amount_usd) },
            { key: 'date', header: 'Date', render: (r) => displayValue(r.payment_date) },
            { key: 'filed', header: 'Filed status', render: (r) => displayValue(r.filed_status) },
            { key: 'status', header: 'Review status', render: (r) => <StatusBadge value={String(r.review_status)} kind="review" /> },
            {
              key: 'open',
              header: 'Case',
              render: (r) => (
                <Link className="text-primary hover:underline" to={`/reviews/${r.review_id}`}>
                  Open
                </Link>
              ),
            },
          ]}
        />
      ) : null}
    </div>
  );
}
