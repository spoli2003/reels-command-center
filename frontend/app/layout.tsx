import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "Reels Command Center",
  description: "Centrum dowodzenia treściami social media",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pl">
      <body>{children}</body>
    </html>
  );
}
