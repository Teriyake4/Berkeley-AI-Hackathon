import { Dashboard } from "@/components/Dashboard";

export default async function SessionReplayPage({
  params,
}: {
  params: Promise<{ encounterId: string }>;
}) {
  const { encounterId } = await params;
  return <Dashboard replayEncounterId={encounterId} />;
}
