"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback } from "react";

// Mirrors the gate in middleware.ts / layout.tsx. Constant for the app's
// lifetime, so the conditional hook call below is stable across renders.
const authEnabled =
  process.env.NEXT_PUBLIC_ENABLE_AUTH === "true" ||
  (process.env.NEXT_PUBLIC_ENABLE_AUTH !== "false" &&
    process.env.NODE_ENV === "production");

/**
 * Returns a function that produces the Authorization header for API calls.
 * The backend derives the tenant from this verified Clerk token — never from a
 * client-supplied id. With auth disabled it returns no header (single tenant).
 */
const NO_HEADERS = async (): Promise<Record<string, string>> => ({});

export function useAuthHeaders(): () => Promise<Record<string, string>> {
  if (!authEnabled) {
    return NO_HEADERS;
  }
  // eslint-disable-next-line react-hooks/rules-of-hooks -- authEnabled is a stable module constant
  const { getToken } = useAuth();
  // Memoized so callers can safely list the returned function in hook deps.
  // eslint-disable-next-line react-hooks/rules-of-hooks -- same stable branch as above
  return useCallback(async () => {
    const token = await getToken();
    const headers: Record<string, string> = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    return headers;
  }, [getToken]);
}
