import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Camino",
  description: "Spanish learning roadmap UI",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
