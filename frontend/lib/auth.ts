import { api, post } from "@/lib/api";
import type { User } from "@/lib/types";

export const emailLoginPath =
  process.env.NEXT_PUBLIC_AUTH_LOGIN_PATH || "/auth/login";

export async function signInWithEmail(email: string, password: string) {
  await post(emailLoginPath, { email, password });
  return verifySession();
}

export async function signUpWithEmail(
  name: string,
  email: string,
  password: string,
) {
  await post("/auth/signup", { name, email, password });
  return verifySession();
}

export async function verifySession() {
  const user = await api<User>("/auth/me", {
    signal: AbortSignal.timeout(15000),
  });
  if (!user?.id || user.local)
    throw new Error("We couldn’t verify your sign-in. Please try again.");
  return user;
}
