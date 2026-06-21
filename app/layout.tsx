import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nos — AI Paramedic Copilot",
  description: "Real-time AI teammate for paramedics — scene to hospital handoff",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
