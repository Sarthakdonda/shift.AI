import Link from "next/link";
import { AlertCircle, LoaderCircle, ArrowRight } from "lucide-react";
export function Loading({
  label = "Loading your workspace…",
}: {
  label?: string;
}) {
  return (
    <div className="loading-state" role="status">
      <LoaderCircle className="spin" size={24} />
      <p>{label}</p>
    </div>
  );
}
export function ErrorBox({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="error-box" role="alert">
      <AlertCircle size={18} />
      <div>
        {message}
        {onRetry && (
          <button className="text-button" onClick={onRetry}>
            Try again <ArrowRight size={14} />
          </button>
        )}
      </div>
    </div>
  );
}
export function Empty({
  title,
  description,
  href,
  action,
}: {
  title: string;
  description: string;
  href?: string;
  action?: string;
}) {
  return (
    <div className="empty-state">
      <div className="empty-symbol">
        <ArrowRight size={26} />
      </div>
      <h2>{title}</h2>
      <p>{description}</p>
      {href && (
        <Link href={href} className="button button-primary">
          {action || "Continue"}
          <ArrowRight size={16} />
        </Link>
      )}
    </div>
  );
}
