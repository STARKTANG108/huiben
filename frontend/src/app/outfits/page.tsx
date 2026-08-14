import { redirect } from "next/navigation";

/** 时尚大片已改为人生副本 */
export default function OutfitsRedirectPage() {
  redirect("/life");
}
