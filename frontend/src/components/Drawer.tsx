import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type { ReactNode } from 'react';

export function Drawer({
  open,
  onOpenChange,
  title,
  children,
  wide = true,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/30 drawer-enter" />
        <Dialog.Content
          className={`fixed right-0 top-0 z-50 flex h-full w-full flex-col bg-white shadow-2xl drawer-enter focus:outline-none ${
            wide ? 'md:w-[80vw]' : 'md:w-[480px]'
          }`}
          aria-label={title || 'Details drawer'}
        >
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <Dialog.Title className="text-base font-semibold text-foreground">{title || 'Details'}</Dialog.Title>
            <Dialog.Close asChild>
              <button type="button" className="rounded-md p-1.5 text-muted hover:bg-slate-100" aria-label="Close drawer">
                <X size={18} />
              </button>
            </Dialog.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-auto">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
