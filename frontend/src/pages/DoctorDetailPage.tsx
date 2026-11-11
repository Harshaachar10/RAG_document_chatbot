import { useParams } from 'react-router-dom';
import { DoctorProfile } from '../features/doctors/components/DoctorProfile';
import { useUrlState } from '../hooks/useUrlState';

export function DoctorDetailPage() {
  const { doctorId = '' } = useParams();
  const { get, setMany } = useUrlState();
  const tab = get('tab', 'overview');

  return <DoctorProfile doctorId={doctorId} tab={tab} onTabChange={(next) => setMany({ tab: next })} />;
}
