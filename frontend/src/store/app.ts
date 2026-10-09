import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Role = "administrator" | "operations" | "sustainability";
export interface User { username: string; name: string; role: Role; permissions: string[]; home: string }
interface AppState {
  token: string | null; user: User | null; facility: string; days: number; theme: "light" | "dark"; lang: "en" | "hi";
  login: (token: string, user: User) => void; logout: () => void;
  setFacility: (f: string) => void; setDays: (d: number) => void; setTheme: (t: "light" | "dark") => void; setLang: (l: "en" | "hi") => void;
}
export const useApp = create<AppState>()(persist((set) => ({
  token: null, user: null, facility: "engineering_college", days: 14, theme: "light", lang: "en",
  login: (token, user) => set({ token, user }), logout: () => set({ token: null, user: null }),
  setFacility: (facility) => set({ facility }), setDays: (days) => set({ days }), setTheme: (theme) => set({ theme }), setLang: (lang) => set({ lang }),
}), { name: "estateiq" }));
