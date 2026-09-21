"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/components/providers";

/**
 * Screens behind sign-in send unauthenticated visitors to the access screen
 * instead of rendering an empty workspace.
 */
export function useRequireAuth() {
  const router = useRouter();
  const { user, loading } = useSession();
  const signedIn = !!user && !user.local;
  useEffect(() => {
    if (!loading && !signedIn) router.replace("/login");
  }, [loading, signedIn, router]);
  return { ready: !loading && signedIn, loading, user };
}
