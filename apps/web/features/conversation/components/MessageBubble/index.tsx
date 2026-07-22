interface Props {
  role: "user" | "assistant";
  content: string;
}

export default function MessageBubble({
  role,
  content,
}: Props) {
  const isUser = role === "user";

  return (
    <div
      className={`mb-6 flex ${
        isUser ? "justify-end" : "justify-start"
      }`}
    >
      <div
        className={`max-w-xl rounded-3xl px-5 py-4 ${
          isUser
            ? "bg-white text-black"
            : "bg-neutral-900 text-white"
        }`}
      >
        {content}
      </div>
    </div>
  );
}