import type { Metadata } from "next";
import { Geist } from "next/font/google";
import { NiprixAuthProvider } from "@/components/niprix-auth-provider";
import { ThemeProvider } from "@/components/theme-provider";
import "./globals.css";

const geist = Geist({ variable: "--font-geist", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "NIPRIX | Enterprise CRM", template: "%s | NIPRIX" },
  description: "NIPRIX enterprise real estate CRM.",
  icons: { icon: "/icon.png" },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  const themeBootScript = `(() => { try { const saved = localStorage.getItem('niprix-theme'); const theme = saved === 'day' || saved === 'night' ? saved : (matchMedia('(prefers-color-scheme: dark)').matches ? 'night' : 'day'); document.documentElement.dataset.theme = theme; document.documentElement.style.colorScheme = theme === 'night' ? 'dark' : 'light'; } catch (_) {} })();`;
  return <html lang="en" className={geist.variable} suppressHydrationWarning><head><script dangerouslySetInnerHTML={{ __html: themeBootScript }} /></head><body><ThemeProvider><NiprixAuthProvider>{children}</NiprixAuthProvider></ThemeProvider></body></html>;
}
