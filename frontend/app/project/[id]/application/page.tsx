"use client";
import { use } from "react";
import { Shell } from "@/components/layout/shell";
import { ApplicationBuilder } from "@/components/application/builder";

export default function ApplicationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <Shell projectId={id} projectName="Application studio"><ApplicationBuilder projectId={id}/></Shell>;
}
