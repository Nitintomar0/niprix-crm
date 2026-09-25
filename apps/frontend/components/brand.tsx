import Image from "next/image";

export function BrandMark({ className = "" }: { className?: string }) {
  return <Image className={`object-contain ${className}`} src="/brand/niprix-mark.png" alt="NIPRIX" width={540} height={530} priority />;
}

export function FullLogo({ className = "" }: { className?: string }) {
  return <Image className={`object-contain ${className}`} src="/brand/niprix-logo.png" alt="NIPRIX — Connect to everyone" width={1536} height={1024} priority />;
}
