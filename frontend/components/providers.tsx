"use client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { api, post } from "@/lib/api";
import type { Health, User } from "@/lib/types";
type Session = {
  user: User | null;
  health: Health | null;
  loading: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
};
const Context = createContext<Session>({
  user: null,
  health: null,
  loading: true,
  refresh: async () => {},
  logout: async () => {},
});
export function Providers({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    const [h, u] = await Promise.allSettled([
      api<Health>("/health"),
      api<User>("/auth/me"),
    ]);
    setHealth(h.status === "fulfilled" ? h.value : null);
    setUser(u.status === "fulfilled" ? u.value : null);
    setLoading(false);
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  return (
    <Context.Provider
      value={{
        user,
        health,
        loading,
        refresh,
        logout: async () => {
          await post("/auth/logout");
          setUser(null);
        },
      }}
    >
      {children}
    </Context.Provider>
  );
}
export const useSession = () => useContext(Context);
