import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";

const geist = Geist({ variable: "--font-geist", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "NIPRIX | Enterprise CRM", template: "%s | NIPRIX" },
  description: "NIPRIX enterprise real estate CRM.",
  icons: { icon: "/icon.png" },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return <html lang="en" className={geist.variable}><body>{children}</body></html>;
}
