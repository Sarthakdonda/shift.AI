"use client";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
  icon,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  children: React.ReactNode;
  icon?: React.ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="modal-overlay" />
        <Dialog.Content
          className="modal"
          onOpenAutoFocus={(event) => {
            const cancel = document.querySelector<HTMLElement>(
              ".modal [data-dialog-cancel]",
            );
            if (cancel) {
              event.preventDefault();
              cancel.focus();
            }
          }}
        >
          {icon && <span className="dialog-icon">{icon}</span>}
          <Dialog.Title className="modal-title">{title}</Dialog.Title>
          <Dialog.Description className="muted">
            {description}
          </Dialog.Description>
          <Dialog.Close
            className="icon-button modal-close"
            aria-label="Close dialog"
          >
            <X size={18} />
          </Dialog.Close>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
