import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export interface TaxpayerProfile {
  name: string;
  vrn: string;
  email: string;
  phone: string;
  address: string;
}

interface UserProfileState {
  taxpayer: TaxpayerProfile;
  setTaxpayer: (patch: Partial<TaxpayerProfile>) => void;
  setVrn: (vrn: string) => void;
  clear: () => void;
}

const emptyTaxpayer: TaxpayerProfile = {
  name: '',
  vrn: '',
  email: '',
  phone: '',
  address: '',
};

export const useUserProfile = create<UserProfileState>()(
  persist(
    (set) => ({
      taxpayer: emptyTaxpayer,
      setTaxpayer: (patch) =>
        set((s) => ({ taxpayer: { ...s.taxpayer, ...patch } })),
      setVrn: (vrn) =>
        set((s) => ({ taxpayer: { ...s.taxpayer, vrn } })),
      clear: () => set({ taxpayer: emptyTaxpayer }),
    }),
    {
      name: 'taxagent.userProfile.v1',
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
