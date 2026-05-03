import type { Metadata } from "next";
import { Syne, Sora, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const fontDisplay = Syne({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["400", "500", "600", "700", "800"],
});

const fontBody = Sora({
  subsets: ["latin"],
  variable: "--font-body",
  weight: ["300", "400", "500", "600"],
});

const fontMono = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "SENTINEL | Agentic AI IoT Security",
  description: "Autonomous network security for the modern home.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${fontDisplay.variable} ${fontBody.variable} ${fontMono.variable} h-full`}>
      <body className="h-full">
        {children}
      </body>
    </html>
  );
}
