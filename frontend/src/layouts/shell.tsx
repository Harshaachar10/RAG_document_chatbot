import { createContext, useContext } from 'react';

type ShellApi = {
  setSubtitle: (value: string) => void;
  openAsk: (doctorId?: string) => void;
  openUpload: () => void;
  openHow: (tab?: string) => void;
};

export const ShellContext = createContext<ShellApi>({
  setSubtitle: () => undefined,
  openAsk: () => undefined,
  openUpload: () => undefined,
  openHow: () => undefined,
});

export function useShell() {
  return useContext(ShellContext);
}
