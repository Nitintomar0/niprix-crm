"use client";
import { useParams } from "next/navigation";
import { NiprixApp } from "@/components/niprix-app";
export default function EmployeePage() { const params = useParams<{ id: string }>(); return <NiprixApp page="employee" employeeId={Number(params.id)} />; }
