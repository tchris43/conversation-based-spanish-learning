const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

export type UserRecord = {
  user_id: string;
  display_name: string;
};

export type RoadmapResponse = {
  user_id: string;
  goal_summary: string;
  best_guess_level: string;
  time_constraint: string;
  state_summary: string;
  gameplan_state: {
    roadmap_summary?: string;
    modules?: { id?: string; title: string; goal?: string }[];
    spaced_review_seed?: string[];
  };
  spaced_review_state: {
    todays_words?: string[];
  };
  active_module_id?: string;
};

export type SessionResponse = {
  phase: string;
  chat_history: { role: string; content: string }[];
  scenario: string;
  goal_summary: string;
  best_guess_level: string;
  time_constraint: string;
  state_summary: string;
  adjustment_state: string;
  gameplan_state: Record<string, unknown>;
  spaced_review_state: { todays_words?: string[] };
  active_module_id: string;
};

export async function fetchUsers() {
  const response = await fetch(`${API_BASE}/api/users`, { cache: "no-store" });
  if (!response.ok) throw new Error("Failed to load users");
  return response.json() as Promise<{ users: UserRecord[]; current_user_id: string }>;
}

export async function createUser(profileName: string) {
  const response = await fetch(`${API_BASE}/api/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_name: profileName }),
  });
  if (!response.ok) throw new Error("Failed to create user");
  return response.json() as Promise<{ user: UserRecord; current_user_id: string }>;
}

export async function selectUser(userId: string) {
  const response = await fetch(`${API_BASE}/api/users/select`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  });
  if (!response.ok) throw new Error("Failed to select user");
  return response.json();
}

export async function fetchRoadmap(userId?: string) {
  const url = new URL(`${API_BASE}/api/roadmap`);
  if (userId) url.searchParams.set("user_id", userId);
  const response = await fetch(url.toString(), { cache: "no-store" });
  if (!response.ok) throw new Error("Failed to load roadmap");
  return response.json() as Promise<RoadmapResponse>;
}

export async function startModule(userId: string, moduleId: string) {
  const response = await fetch(`${API_BASE}/api/session/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, module_id: moduleId }),
  });
  if (!response.ok) throw new Error("Failed to start module");
  return response.json() as Promise<{
    module: { id: string; title: string; goal: string; scenario: string; completion_signal: string };
    session: SessionResponse;
  }>;
}

export async function fetchCurrentSession(userId?: string) {
  const url = new URL(`${API_BASE}/api/session/current`);
  if (userId) url.searchParams.set("user_id", userId);
  const response = await fetch(url.toString(), { cache: "no-store" });
  if (!response.ok) throw new Error("Failed to load session");
  return response.json() as Promise<SessionResponse>;
}

export async function sendChatMessage(userId: string, message: string) {
  const response = await fetch(`${API_BASE}/api/chat/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, message }),
  });
  if (!response.ok) throw new Error("Failed to send message");
  return response.json() as Promise<SessionResponse>;
}

export async function fetchLatestAssistantAudio(userId: string) {
  const url = new URL(`${API_BASE}/api/audio/latest`);
  url.searchParams.set("user_id", userId);
  const response = await fetch(url.toString(), { cache: "no-store" });
  if (!response.ok) throw new Error("Failed to load assistant audio");
  return response.blob();
}
