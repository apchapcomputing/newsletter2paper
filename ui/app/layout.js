import { Atkinson_Hyperlegible, Courier_Prime, Unbounded, UnifrakturCook } from "next/font/google";
import "./globals.css";
import { AppRouterCacheProvider } from '@mui/material-nextjs/v15-appRouter';
import Providers from '../contexts/providers';

// The four faces of the design system, one job each: blackletter masthead, display headings
// and buttons, sans reading text, typewriter labels. globals.css maps these variables to --font-*.
const atkinson = Atkinson_Hyperlegible({
  variable: "--font-atkinson",
  subsets: ["latin"],
  weight: ["400", "700"],
  style: ["normal", "italic"],
});

const courier = Courier_Prime({
  variable: "--font-courier",
  subsets: ["latin"],
  weight: ["400", "700"],
});

const unbounded = Unbounded({
  variable: "--font-unbounded",
  subsets: ["latin"],
  weight: ["600", "700", "800"],
});

const unifraktur = UnifrakturCook({
  variable: "--font-unifraktur",
  subsets: ["latin"],
  weight: "700",
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
        className={`${atkinson.variable} ${courier.variable} ${unbounded.variable} ${unifraktur.variable} antialiased`}
      >
        <AppRouterCacheProvider>
          <Providers>
            {children}
          </Providers>
        </AppRouterCacheProvider>
      </body>
    </html>
  );
}
