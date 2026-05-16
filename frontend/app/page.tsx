import { ChatPanel } from "@/components/ChatPanel";

export default function Home() {
  return (
    <main className="flex h-dvh flex-col bg-zinc-950">
      {/* Subtle gradient background */}
      <div
        className="pointer-events-none fixed inset-0 z-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(99,102,241,0.12) 0%, transparent 60%)",
        }}
      />
      <div className="relative z-10 mx-auto flex h-full w-full max-w-2xl flex-col">
        <ChatPanel />
      </div>
    </main>
  );
}
