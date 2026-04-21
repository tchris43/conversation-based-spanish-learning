import Link from "next/link";
import { messages } from "@/lib/mock-data";
import { MountainGraphic } from "./MountainGraphic";

type SessionShellProps = {
  moduleTitle: string;
};

export function SessionShell({ moduleTitle }: SessionShellProps) {
  return (
    <main className="session-page">
      <div className="session-fade">
        <MountainGraphic faded />
      </div>

      <div className="session-shell">
        <div className="session-topbar">
          <div className="session-left">
            <Link href="/" className="back-button">
              ←
            </Link>
            <div className="chip">Taylor</div>
          </div>
          <div className="chip">Read replies aloud</div>
        </div>

        <section className="session-card">
          <div className="session-card-topbar">
            <div className="chip">{moduleTitle}</div>
          </div>

          <div className="session-chat">
            {messages.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={`bubble ${message.role === "assistant" ? "assistant" : "user"}`}
              >
                {message.content}
              </div>
            ))}
          </div>

          <div className="session-composer">
            <input className="session-input" defaultValue="Me gusta preparar comida mexicana." />
            <div className="session-actions">
              <div />
              <button className="session-send">Send</button>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
