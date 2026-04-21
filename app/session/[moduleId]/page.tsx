import { SessionPageClient } from "@/components/SessionPageClient";

type SessionPageProps = {
  params: { moduleId: string };
  searchParams: { user?: string };
};

export default function SessionRoute({ params, searchParams }: SessionPageProps) {
  const userId = searchParams.user ?? "local-dev-user";
  return <SessionPageClient moduleId={params.moduleId} userId={userId} />;
}
