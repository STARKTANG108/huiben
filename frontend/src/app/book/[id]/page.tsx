import { Workbench } from "@/components/pipeline/Workbench";

export default async function BookProjectPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <main className="min-h-screen pb-16">
      <Workbench projectId={id} mode="book" />
    </main>
  );
}
