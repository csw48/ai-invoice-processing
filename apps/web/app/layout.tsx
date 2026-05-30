import { ClerkProvider, SignedIn, SignedOut, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";
import type { Metadata } from "next";
import { JetBrains_Mono, Plus_Jakarta_Sans, Spectral } from "next/font/google";
import Link from "next/link";
import { NavLinks } from "../components/nav-links";
import "./globals.css";

const spectral = Spectral({
  subsets: ["latin"],
  weight: ["300", "400", "500"],
  variable: "--font-spectral",
  display: "swap",
});

const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-jakarta",
  display: "swap",
});

const jbm = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-jbm",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Factura — AI Invoice Processing",
  description: "Upload, review, and export invoice data for Slovak SMBs",
};

const authEnabled =
  process.env.NEXT_PUBLIC_ENABLE_AUTH === "true" ||
  (process.env.NEXT_PUBLIC_ENABLE_AUTH !== "false" && process.env.NODE_ENV === "production");

function AuthControls() {
  if (!authEnabled) {
    return null;
  }

  return (
    <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "12px" }}>
      <SignedOut>
        <SignInButton mode="modal">
          <button className="btn btn-ghost btn-sm">Sign in</button>
        </SignInButton>
        <SignUpButton mode="modal">
          <button className="btn btn-accent btn-sm">Get started</button>
        </SignUpButton>
      </SignedOut>
      <SignedIn>
        <UserButton />
      </SignedIn>
    </div>
  );
}

function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <html lang="sk" className={`${spectral.variable} ${jakarta.variable} ${jbm.variable}`}>
      <body>
        <nav className="top-nav">
          <div className="nav-inner">
            <Link href="/" className="nav-brand">
              <div className="nav-brand-icon">F</div>
              <span className="nav-brand-name">Factura</span>
            </Link>
            <NavLinks />
            <AuthControls />
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  if (!authEnabled) {
    return <AppShell>{children}</AppShell>;
  }

  return (
    <ClerkProvider>
      <AppShell>{children}</AppShell>
    </ClerkProvider>
  );
}
