import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Invoice Processing",
  description: "Upload, review, and export invoice data for Slovak SMBs",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
