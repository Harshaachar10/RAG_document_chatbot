import {
  Activity,
  ClipboardList,
  Database,
  FileUp,
  LayoutDashboard,
  NotebookPen,
  ShieldCheck,
  Users,
} from 'lucide-react';

export const NAV_ITEMS = [
  { to: '/overview', label: 'Overview', icon: LayoutDashboard },
  { to: '/upload', label: 'Upload & Match', icon: FileUp },
  { to: '/golden-records', label: 'Golden Records', icon: Users },
  { to: '/reviews', label: 'Review Center', icon: ClipboardList },
  { to: '/payment-compliance', label: 'Payment Compliance', icon: ShieldCheck },
  { to: '/notes-insights', label: 'Notes Insights', icon: NotebookPen },
  { to: '/sources', label: 'Data Sources', icon: Database },
  { to: '/quality', label: 'Quality & Audit', icon: Activity },
] as const;
