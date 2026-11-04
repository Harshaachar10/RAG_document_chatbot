import * as RadixDialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type { ReactNode } from 'react';

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-40 bg-black/40" />
        <RadixDialog.Content
          className="fixed left-1/2 top-1/2 z-50 w-[min(560px,92vw)] -translate-x-1/2 -translate-y-1/2 rounded-[12px] border border-border bg-white p-5 shadow-xl focus:outline-none"
          aria-describedby={description ? 'dialog-desc' : undefined}
        >
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <RadixDialog.Title className="text-lg font-semibold text-foreground">{title}</RadixDialog.Title>
              {description ? (
                <RadixDialog.Description id="dialog-desc" className="mt-1 text-sm text-muted">
                  {description}
                </RadixDialog.Description>
              ) : null}
            </div>
            <RadixDialog.Close asChild>
              <button type="button" className="rounded-md p-1 text-muted hover:bg-slate-100" aria-label="Close dialog">
                <X size={18} />
              </button>
            </RadixDialog.Close>
          </div>
          <div>{children}</div>
          {footer ? <div className="mt-5 flex justify-end gap-2">{footer}</div> : null}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
