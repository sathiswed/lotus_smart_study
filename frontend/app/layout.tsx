import type { Metadata, Viewport } from "next";
import "./globals.css";
import { AuthProvider } from "@/components/AuthProvider";

export const metadata: Metadata = {
  title: { default: "Lotus Smart Study", template: "%s | Lotus Smart Study" },
  description: "Teacher-guided, textbook-grounded assessments for learning, thinking and growth.",
  applicationName: "Lotus Smart Study",
  icons: { icon: "/lotus_logo_new.png", apple: "/lotus_logo_new.png" },
};
export const viewport: Viewport = { themeColor: "#087FC4", colorScheme: "light" };
export default function RootLayout({ children }: Readonly<{children: React.ReactNode}>) { return <html lang="en"><body><AuthProvider>{children}</AuthProvider></body></html>; }
