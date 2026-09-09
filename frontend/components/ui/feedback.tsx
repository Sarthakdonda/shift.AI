"use client";

import { T } from "@/components/locale";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  Check,
  Info,
  LoaderCircle,
  LogOut,
  TriangleAlert,
  X,
} from "lucide-react";
import { Modal } from "./dialog";

type Toast = {
  id: number;
  message: string;
  tone: "success" | "info" | "error";
};
const FeedbackContext = createContext<
  (message: string, tone?: Toast["tone"]) => void
>(() => {});
export const useToast = () => useContext(FeedbackContext);

export function FeedbackProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const counter = useRef(0);
  useEffect(() => () => timers.current.forEach(clearTimeout), []);
  const notify = useCallback(
    (message: string, tone: Toast["tone"] = "success") => {
      const id = ++counter.current;
      setToasts((previous) => [...previous.slice(-2), { id, message, tone }]);
      timers.current.push(
        setTimeout(
          () => setToasts((previous) => previous.filter((t) => t.id !== id)),
          6000,
        ),
      );
    },
    [],
  );
  return (
    <FeedbackContext.Provider value={notify}>
      {children}
      <div className="toast-stack" aria-label="Notifications">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`toast toast-${toast.tone}`}
            role={toast.tone === "error" ? "alert" : "status"}
          >
            {toast.tone === "success" ? (
              <Check size={19} />
            ) : toast.tone === "error" ? (
              <TriangleAlert size={19} />
            ) : (
              <Info size={19} />
            )}
            <p>{toast.message}</p>
            <button
              aria-label="Dismiss notification"
              onClick={() =>
                setToasts((previous) =>
                  previous.filter((t) => t.id !== toast.id),
                )
              }
            >
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
    </FeedbackContext.Provider>
  );
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  onConfirm,
  danger = false,
  signout = false,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => void | Promise<void>;
  danger?: boolean;
  signout?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <Modal
      open={open}
      onOpenChange={(value) => {
        if (!busy) {
          setError("");
          onOpenChange(value);
        }
      }}
      title={title}
      description={description}
      icon={signout ? <LogOut size={23} /> : <TriangleAlert size={23} />}
    >
      {error && (
        <p role="alert" className="dialog-error">
          {error}
        </p>
      )}
      <div className="modal-actions">
        <button
          data-dialog-cancel
          className="button button-secondary"
          disabled={busy}
          onClick={() => {
            setError("");
            onOpenChange(false);
          }}
        >
          <T text={"Cancel"} />
        </button>
        <button
          className={`button ${danger ? "button-danger" : "button-primary"}`}
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              await onConfirm();
              onOpenChange(false);
            } catch (e) {
              setError(
                e instanceof Error
                  ? e.message
                  : "Something went wrong. Please try again.",
              );
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy && <LoaderCircle size={16} className="spin" />}
          {busy ? "Please wait…" : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
