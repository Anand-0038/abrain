import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "A-Brain | Agent continuity",
  description: "A living 2D world where agent memory survives the session.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
