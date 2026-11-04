import {
  Activity,
  ClipboardList,
  Database,
  LayoutDashboard,
  Users,
} from 'lucide-react';

export const NAV_ITEMS = [
  { to: '/overview', label: 'Overview', icon: LayoutDashboard },
  { to: '/golden-records', label: 'Golden Records', icon: Users },
  { to: '/reviews', label: 'Review Center', icon: ClipboardList },
  { to: '/sources', label: 'Sources & Processing', icon: Database },
  { to: '/quality', label: 'Quality & Activity', icon: Activity },
] as const;
