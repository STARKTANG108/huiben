import { redirect } from "next/navigation";

export default async function OutfitsIdRedirect({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await params;
  redirect("/life");
}
