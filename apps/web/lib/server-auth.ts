import { auth } from "@clerk/nextjs/server";

const authEnabled =
  process.env.NEXT_PUBLIC_ENABLE_AUTH === "true" ||
  (process.env.NEXT_PUBLIC_ENABLE_AUTH !== "false" &&
    process.env.NODE_ENV === "production");

/**
 * Authorization header for API calls made from server components.
 * Returns the verified Clerk session token, or no header when auth is disabled.
 */
export async function serverAuthHeaders(): Promise<Record<string, string>> {
  if (!authEnabled) return {};
  const { getToken } = await auth();
  const token = await getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
