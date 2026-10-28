import { notFound } from "next/navigation";
import { NiprixApp } from "@/components/niprix-app";

export default async function CustomerAccountPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const customerId = Number(id);
  if (!Number.isInteger(customerId) || customerId < 1) notFound();
  return <NiprixApp page="accounts" customerId={customerId} />;
}
