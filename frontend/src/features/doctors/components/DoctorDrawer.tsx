import { Drawer } from '../../../components/Drawer';
import { DoctorProfile } from './DoctorProfile';

export function DoctorDrawer({
  doctorId,
  open,
  onOpenChange,
  tab,
  onTabChange,
}: {
  doctorId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tab: string;
  onTabChange: (tab: string) => void;
}) {
  return (
    <Drawer open={open} onOpenChange={onOpenChange} title="Doctor profile" wide>
      {doctorId ? (
        <DoctorProfile doctorId={doctorId} tab={tab} onTabChange={onTabChange} />
      ) : null}
    </Drawer>
  );
}
