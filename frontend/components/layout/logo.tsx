import { T } from "@/components/locale";
import Image from "next/image";
import Link from "next/link";
import mark from "@/public/brand/logo-mark.png";

/**
 * shift.AI lockup: the extracted mark (transparent PNG) plus the wordmark.
 * `light` inverts the wordmark for navy surfaces.
 */
export function Logo({
  light = false,
  size = "md",
  href = "/",
}: {
  light?: boolean;
  size?: "md" | "lg";
  href?: string;
}) {
  return (
    <Link
      href={href}
      className={`logo ${light ? "logo-light" : ""} ${size === "lg" ? "logo-lg" : ""}`}
      aria-label="shift.AI home"
    >
      <span className="logo-mark">
        <Image
          src={mark}
          alt=""
          priority
          sizes="28px"
          style={{
            width: "auto",
            height: "100%",
            maxWidth: "100%",
            objectFit: "contain",
          }}
        />
      </span>
      <span className="logo-word">
        <T text={"shift"} />
        <span className="logo-ai">
          <T text={".AI"} />
        </span>
      </span>
    </Link>
  );
}
