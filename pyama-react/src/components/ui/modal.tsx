import type { ReactNode } from "react";
import { useEffect } from "react";

interface ModalProps {
  title: string;
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
}

export function Modal({ title, isOpen, onClose, children }: ModalProps) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      <div
        className="relative w-[90vw] h-[90vh] rounded-lg shadow-2xl flex flex-col overflow-hidden border border-border"
        style={{ backgroundColor: "var(--color-card)" }}
      >
        <div
          className="flex items-center justify-between px-4 py-3 border-b border-border"
          style={{ backgroundColor: "var(--color-background)" }}
        >
          <h2 className="text-lg font-semibold text-foreground-bright">
            {title}
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-accent transition-colors"
            aria-label="Close"
          >
            <svg
              className="w-5 h-5 text-muted-foreground"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-auto p-4">{children}</div>
      </div>
    </div>
  );
}
