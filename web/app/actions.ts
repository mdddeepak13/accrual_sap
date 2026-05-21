"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { startRun } from "@/lib/api";

export async function startRunAction(): Promise<void> {
  const { run_id } = await startRun();
  revalidatePath("/");
  redirect(`/runs/${run_id}`);
}
