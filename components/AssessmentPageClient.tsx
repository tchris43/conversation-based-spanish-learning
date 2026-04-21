"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  fetchUsers,
  fetchRoadmap,
  fetchCurrentSession,
  fetchLatestAssistantAudio,
  selectUser,
  createUser,
  sendChatMessage,
  type SessionResponse,
  type UserRecord,
  type RoadmapResponse,
} from "@/lib/api";

const isAtLeastOneModule = (roadmap?: RoadmapResponse) => {
  return (roadmap?.gameplan_state?.modules?.length ?? 0) > 0;
};

export function AssessmentPageClient() {
  const router = useRouter();
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [currentUserId, setCurrentUserId] = useState("");
  const [newProfileName, setNewProfileName] = useState("");
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [roadmapReady, setRoadmapReady] = useState(false);
  const [audioEnabled, setAudioEnabled] = useState(false);
  const [shouldPlayNextReply, setShouldPlayNextReply] = useState(false);
  const lastPlayedAssistantTextRef = useRef("");

  const guardRoadmapRedirect = (roadmap: RoadmapResponse | null) => {
    const ready = Boolean(roadmap && isAtLeastOneModule(roadmap));
    setRoadmapReady(ready);
    if (ready) {
      // AUDIT: routing is based on module count; partial roadmaps may look empty briefly so keep this check synchronized with backend readiness.
      router.replace("/roadmap");
    }
  };

  const loadForUser = async (userId: string) => {
    try {
      const roadmap = await fetchRoadmap(userId);
      guardRoadmapRedirect(roadmap);
      if (!isAtLeastOneModule(roadmap)) {
        const currentSession = await fetchCurrentSession(userId);
        setSession(currentSession);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load session");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const init = async () => {
      try {
        const userData = await fetchUsers();
        setUsers(userData.users);
        setCurrentUserId(userData.current_user_id);
        await loadForUser(userData.current_user_id);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load user data");
        setLoading(false);
      }
    };
    void init();
  }, []);

  useEffect(() => {
    if (!audioEnabled || !shouldPlayNextReply || !session?.chat_history?.length || !currentUserId) {
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
        const blob = await fetchLatestAssistantAudio(currentUserId);
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
  }, [audioEnabled, currentUserId, session, shouldPlayNextReply]);

  const handleUserChange = async (userId: string) => {
    setCurrentUserId(userId);
    await selectUser(userId);
    setLoading(true);
    await loadForUser(userId);
  };

  const handleCreate = async () => {
    if (!newProfileName.trim()) return;
    try {
      const created = await createUser(newProfileName);
      setUsers((prev) => [...prev, created.user]);
      setCurrentUserId(created.current_user_id);
      await loadForUser(created.current_user_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create user");
    } finally {
      setNewProfileName("");
    }
  };

  const handleSend = async () => {
    const trimmedMessage = message.trim();
    if (!trimmedMessage || !currentUserId || isSubmitting) return;
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
      const updated = await sendChatMessage(currentUserId, trimmedMessage);
      setSession(updated);
      setShouldPlayNextReply(true);
      const roadmap = await fetchRoadmap(currentUserId);
      guardRoadmapRedirect(roadmap);
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
        <div className="session-gradient" />
      </div>

      <div className="session-shell">
        <div className="session-topbar">
          <div className="session-left">
            <div className="chip">Onboarding</div>
            <select
              className="chip chip-select"
              value={currentUserId}
              onChange={(e) => void handleUserChange(e.target.value)}
            >
              {users.map((user) => (
                <option key={user.user_id} value={user.user_id}>
                  {user.display_name}
                </option>
              ))}
            </select>
            <input
              className="chip chip-input"
              placeholder="New profile"
              value={newProfileName}
              onChange={(e) => setNewProfileName(e.target.value)}
            />
            <button className="chip chip-button" onClick={() => void handleCreate()}>
              Create
            </button>
            {roadmapReady ? (
              <Link href="/roadmap" className="chip chip-button">
                View Roadmap
              </Link>
            ) : null}
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
            <div className="chip">Get to know the learner</div>
          </div>

          <div className="session-chat">
            {loading && <div className="bubble assistant">Loading session...</div>}
            {error && <div className="bubble assistant">{error}</div>}
            {session?.chat_history?.map((item, index) => (
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
              placeholder="Submit a response..."
              disabled={isSubmitting}
            />
            <div className="session-actions">
              <div />
              <button className="session-send" type="submit" disabled={isSubmitting}>
                Share
              </button>
            </div>
          </form>
        </section>
      </div>
    </main>
  );
}
