"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { fetchLatestAssistantAudio, sendChatMessage, startModule, type SessionResponse } from "@/lib/api";
import { MountainGraphic } from "./MountainGraphic";

type SessionPageClientProps = {
  moduleId: string;
  userId: string;
};

export function SessionPageClient({ moduleId, userId }: SessionPageClientProps) {
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [moduleTitle, setModuleTitle] = useState(moduleId.replace(/-/g, " "));
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [audioEnabled, setAudioEnabled] = useState(false);
  const [shouldPlayNextReply, setShouldPlayNextReply] = useState(false);
  const lastPlayedAssistantTextRef = useRef("");

  useEffect(() => {
    const load = async () => {
      try {
        const started = await startModule(userId, moduleId);
        setSession(started.session);
        setModuleTitle(started.module.title);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to start session");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [moduleId, userId]);

  useEffect(() => {
    if (!audioEnabled || !shouldPlayNextReply || !session?.chat_history?.length) {
      return;
    }
    const latestAssistant = [...session.chat_history].reverse().find((item) => item.role === "assistant");
    const assistantText = latestAssistant?.content?.trim() || "";
    if (!assistantText || assistantText === lastPlayedAssistantTextRef.current) {
      setShouldPlayNextReply(false);
      return;
    }
    let objectUrl = "";
    const play = async () => {
      try {
        const blob = await fetchLatestAssistantAudio(userId);
        objectUrl = URL.createObjectURL(blob);
        const audio = new Audio(objectUrl);
        await audio.play();
        lastPlayedAssistantTextRef.current = assistantText;
      } catch {
        // AUDIT: Browser autoplay rules or missing audio bytes should not break chat flow.
      } finally {
        setShouldPlayNextReply(false);
        if (objectUrl) {
          setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
        }
      }
    };
    void play();
  }, [audioEnabled, session, shouldPlayNextReply, userId]);

  const handleSend = async () => {
    const trimmedMessage = message.trim();
    if (!trimmedMessage || isSubmitting) return;
    const previousSession = session;
    setError("");
    setIsSubmitting(true);
    setMessage("");
    if (previousSession) {
      setSession({
        ...previousSession,
        chat_history: [...previousSession.chat_history, { role: "user", content: trimmedMessage }],
      });
    }
    try {
      const updated = await sendChatMessage(userId, trimmedMessage);
      setSession(updated);
      setShouldPlayNextReply(true);
    } catch (err) {
      setSession(previousSession);
      setError(err instanceof Error ? err.message : "Failed to send message");
      setMessage(trimmedMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="session-page">
      <div className="session-fade">
        <MountainGraphic faded />
      </div>

      <div className="session-shell">
        <div className="session-topbar">
          <div className="session-left">
            <Link href="/roadmap" className="back-button">
              ←
            </Link>
            <div className="chip">{userId}</div>
          </div>
          <button
            className={`chip chip-button ${audioEnabled ? "chip-active" : ""}`}
            type="button"
            onClick={() => setAudioEnabled((value) => !value)}
          >
            {audioEnabled ? "Audio on" : "Audio off"}
          </button>
        </div>

        <section className="session-card">
          <div className="session-card-topbar">
            <div className="chip">{moduleTitle}</div>
          </div>

          <div className="session-chat">
            {loading && <div className="bubble assistant">Starting session...</div>}
            {error && <div className="bubble assistant">{error}</div>}
            {(session?.chat_history ?? []).map((item, index) => (
              <div
                key={`${item.role}-${index}`}
                className={`bubble ${item.role === "assistant" ? "assistant" : "user"}`}
              >
                {item.content}
              </div>
            ))}
          </div>

          <form
            className="session-composer"
            onSubmit={(e) => {
              e.preventDefault();
              void handleSend();
            }}
          >
            <input
              className="session-input"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Reply in Spanish..."
              disabled={isSubmitting}
            />
            <div className="session-actions">
              <div />
              <button className="session-send" type="submit" disabled={isSubmitting}>
                Send
              </button>
            </div>
          </form>
        </section>
      </div>
    </main>
  );
}
