import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "KrishiMandi Intelligence | कृषि मंडी | ಕೃಷಿ ಮಂಡಿ",
  description:
    "Real-Time APMC Mandi Price Intelligence, Historical Analytics, Weather Risk Indicators & NVIDIA NIM Farmer Advisory Copilot",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "KrishiMandi",
  },
};

export const viewport: Viewport = {
  themeColor: "#15803d",
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} font-sans antialiased bg-slate-100 text-slate-900`}>
        {children}
      </body>
    </html>
  );
}
