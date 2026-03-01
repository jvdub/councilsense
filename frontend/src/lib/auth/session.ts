import { cookies } from "next/headers";

export async function getAuthTokenFromCookie(): Promise<string | null> {
  const requestCookies = await cookies();
  const cookieToken = requestCookies.get("auth_token")?.value ?? null;
  if (cookieToken) {
    return cookieToken;
  }

  const authGuardDisabled = process.env.NEXT_PUBLIC_DISABLE_AUTH_GUARD === "true";
  if (!authGuardDisabled) {
    return null;
  }

  return process.env.NEXT_PUBLIC_LOCAL_DEV_AUTH_TOKEN ?? "local-dev-bypass-token";
}