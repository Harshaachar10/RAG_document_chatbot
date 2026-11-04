import { useQuery } from '@tanstack/react-query';
import { NavLink, Outlet } from 'react-router-dom';
import { fetchHealth } from '../api/dashboard';
import { NAV_ITEMS } from '../config/navigation';
import { cn } from '../utils/formatters';

export function AppLayout() {
  const health = useQuery({ queryKey: ['health'], queryFn: ({ signal }) => fetchHealth(signal) });
  const aiReady = health.data?.ai_ready;
  const missing = health.data?.missing_ai_settings || [];
  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="flex w-64 shrink-0 flex-col bg-sidebar text-white">
        <div className="border-b border-white/10 px-4 py-4">
          <img
            src="/assets/logos/affine-placeholder.svg"
            alt="Affine Analytics"
            className="h-10 w-auto"
          />
          <div className="mt-3 text-sm font-semibold">Doctor Intelligence</div>
          <div className="mt-2 inline-flex rounded-md bg-white/10 px-2 py-1 text-[11px] text-slate-200">
            Synthetic data
          </div>
          <div className="mt-1 text-[11px] text-slate-300">
            {health.isError
              ? 'API unavailable'
              : aiReady
                ? 'Azure OpenAI configured for explicit analysis'
                : missing.length
                  ? `AI unavailable. Missing ${missing.join(', ')}`
                  : 'Prepared profiles load without a model call'}
          </div>
        </div>
        <nav className="flex-1 space-y-1 px-2 py-4" aria-label="Primary">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-2 rounded-md px-3 py-2 text-sm transition',
                    isActive ? 'bg-white/15 font-semibold text-white' : 'text-slate-200 hover:bg-white/10',
                  )
                }
              >
                <Icon size={16} aria-hidden />
                {item.label}
              </NavLink>
            );
          })}
        </nav>
        <div className="border-t border-white/10 px-4 py-3 text-[11px] text-slate-300">
          Affine Analytics — Doctor Intelligence
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <main className="flex-1 px-4 py-4 md:px-6 md:py-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
