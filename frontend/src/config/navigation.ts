import { ClipboardList, LayoutDashboard, Users } from 'lucide-react';

export type NavChild = { to: string; label: string };

export type NavItem = {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  children?: NavChild[];
};

export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/doctors', label: 'Golden Records', icon: Users },
  { to: '/review', label: 'Review', icon: ClipboardList },
];
