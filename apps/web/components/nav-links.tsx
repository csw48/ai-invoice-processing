"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Dashboard", exact: true },
  { href: "/invoices", label: "Invoices", exact: false },
  { href: "/vendors", label: "Vendors", exact: false },
  { href: "/stats", label: "Stats", exact: false },
  { href: "/config", label: "Config", exact: false },
];

export function NavLinks() {
  const pathname = usePathname();

  return (
    <div className="nav-links">
      {LINKS.map(({ href, label, exact }) => {
        const active = exact ? pathname === href : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={active ? "nav-link nav-link-active" : "nav-link"}
          >
            {label}
          </Link>
        );
      })}
    </div>
  );
}
