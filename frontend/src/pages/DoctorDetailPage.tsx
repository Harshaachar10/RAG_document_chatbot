import { useParams } from 'react-router-dom';
import { DoctorProfile } from '../features/doctors/components/DoctorProfile';
import { useUrlState } from '../hooks/useUrlState';

export function DoctorDetailPage() {
  const { doctorId = '' } = useParams();
  const { get, setMany } = useUrlState();
  const tab = get('tab', 'summary');
  const eventId = get('event_id') || null;

  return (
    <div className="overflow-hidden rounded-[12px] border border-border bg-white shadow-sm">
      <DoctorProfile
        doctorId={doctorId}
        mode="page"
        tab={tab}
        onTabChange={(next) => setMany({ tab: next })}
        eventId={eventId}
      />
    </div>
  );
}
