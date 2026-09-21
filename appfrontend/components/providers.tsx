"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { Sparkles } from "lucide-react";
import { api, post } from "@/lib/api";
import type { Health, User } from "@/lib/types";

type Session = {
  user: User | null;
  health: Health | null;
  loading: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
};

const SessionContext = createContext<Session>({
  user: null,
  health: null,
  loading: true,
  refresh: async () => {},
  logout: async () => {},
});

const ToastContext = createContext<(message: string) => void>(() => {});

export function useSession() {
  return useContext(SessionContext);
}

export function useToast() {
  return useContext(ToastContext);
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [loading, setLoading] = useState(true);
  const [toasts, setToasts] = useState<{ id: number; message: string }[]>([]);

  const refresh = useCallback(async () => {
    const [h, u] = await Promise.allSettled([
      api<Health>("/health", { signal: AbortSignal.timeout(10000) }),
      api<User>("/auth/me", { signal: AbortSignal.timeout(10000) }),
    ]);
    setHealth(h.status === "fulfilled" ? h.value : null);
    setUser(u.status === "fulfilled" ? u.value : null);
    setLoading(false);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const notify = useCallback((message: string) => {
    const id = Date.now() + Math.random();
    setToasts((current) => [...current.slice(-2), { id, message }]);
    setTimeout(
      () => setToasts((current) => current.filter((item) => item.id !== id)),
      3200,
    );
  }, []);

  const session = useMemo<Session>(
    () => ({
      user,
      health,
      loading,
      refresh,
      logout: async () => {
        await post("/auth/logout");
        setUser(null);
      },
    }),
    [user, health, loading, refresh],
  );

  return (
    <SessionContext.Provider value={session}>
      <ToastContext.Provider value={notify}>
        {children}
        <div className="toast-layer" aria-live="polite" aria-atomic="false">
          {toasts.map((toast) => (
            <div className="toast" key={toast.id} role="status">
              <Sparkles size={15} aria-hidden="true" />
              <span>{toast.message}</span>
            </div>
          ))}
        </div>
      </ToastContext.Provider>
    </SessionContext.Provider>
  );
}
