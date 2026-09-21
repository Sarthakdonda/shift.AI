"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/components/providers";
import { Splash } from "@/components/ui/states";

/**
 * The app has no landing page. The entry route resolves the saved session and
 * goes straight to the workspace or to sign-in.
 */
export default function Entry() {
  const router = useRouter();
  const { user, loading } = useSession();

  useEffect(() => {
    if (loading) return;
    router.replace(user && !user.local ? "/chats" : "/login");
  }, [loading, user, router]);

  return <Splash />;
}
