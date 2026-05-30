import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const isPublicRoute = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)"]);
const authEnabled =
  process.env.NEXT_PUBLIC_ENABLE_AUTH === "true" ||
  (process.env.NEXT_PUBLIC_ENABLE_AUTH !== "false" && process.env.NODE_ENV === "production");

const authMiddleware = clerkMiddleware(async (auth, request) => {
  if (!isPublicRoute(request)) {
    await auth.protect();
  }
});

function localMiddleware() {
  return NextResponse.next();
}

export default authEnabled ? authMiddleware : localMiddleware;

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
