import { IndicatorDetail } from "@/components/indicator-detail";

export default async function IndicatorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <IndicatorDetail indicatorId={id} />;
}
