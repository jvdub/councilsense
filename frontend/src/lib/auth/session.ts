import { cookies } from "next/headers";

export async function getAuthTokenFromCookie(): Promise<string | null> {
  const requestCookies = await cookies();
  return requestCookies.get("auth_token")?.value ?? null;
}