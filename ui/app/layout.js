import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Providers from '../contexts/providers';
import { Analytics } from '@vercel/analytics/next';

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata = {
  title: "newsletter2paper",
  description: "Convert RSS newsletters into formatted PDFs",
  icons: {
    icon: [
      { url: '/newspaper.svg', type: 'image/svg+xml' },
      { url: '/favicon.ico' }
    ]
  }
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <Providers>
          {children}
        </Providers>
        <Analytics />
      </body>
    </html>
  );
}
