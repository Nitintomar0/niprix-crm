"use client";

import { useParams } from "next/navigation";
import { NiprixApp } from "@/components/niprix-app";

export default function LeadDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  return <NiprixApp page="leads" leadId={Number.isInteger(id) && id > 0 ? id : undefined} />;
}
