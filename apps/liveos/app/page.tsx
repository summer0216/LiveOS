import FirstConversationExperience from '../features/first-conversation/FirstConversationExperience';

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ conversation_id?: string | string[] }>;
}) {
  const params = await searchParams;
  const value = params.conversation_id;
  const initialConversationId = Array.isArray(value) ? value[0] ?? '' : value ?? '';
  return <FirstConversationExperience initialConversationId={initialConversationId} />;
}
