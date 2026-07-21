/**
 * SmartHire AI — Root Layout
 */
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SmartHire AI — ATS Resume Analyzer",
  description:
    "AI-powered ATS resume analyzer: score your resume, match jobs, generate cover letters and interview questions.",
  keywords: ["ATS", "resume analyzer", "job matching", "AI", "cover letter"],
  openGraph: {
    title: "SmartHire AI",
    description: "AI-powered ATS Resume Analyzer",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body>{children}</body>
    </html>
  );
}
