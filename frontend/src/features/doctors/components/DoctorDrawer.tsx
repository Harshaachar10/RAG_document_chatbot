import { Drawer } from '../../../components/Drawer';
import { DoctorProfile } from './DoctorProfile';

export function DoctorDrawer({
  doctorId,
  open,
  onOpenChange,
  tab,
  onTabChange,
  eventId,
}: {
  doctorId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tab: string;
  onTabChange: (tab: string) => void;
  eventId?: string | null;
}) {
  return (
    <Drawer open={open} onOpenChange={onOpenChange} title="Doctor profile" wide>
      {doctorId ? (
        <DoctorProfile
          doctorId={doctorId}
          mode="drawer"
          tab={tab}
          onTabChange={onTabChange}
          onClose={() => onOpenChange(false)}
          expandTo={`/golden-records/${doctorId}?tab=${tab}`}
          eventId={eventId}
        />
      ) : null}
    </Drawer>
  );
}
