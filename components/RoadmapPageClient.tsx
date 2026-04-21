"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchRoadmap, fetchUsers, selectUser, createUser, type RoadmapResponse, type UserRecord } from "@/lib/api";
import { MountainGraphic } from "./MountainGraphic";

type PositionedModule = {
  id: string;
  title: string;
  subtitle: string;
  x: number;
  y: number;
  current?: boolean;
  locked?: boolean;
};

const fallbackPositions = [
  { x: 24, y: 78 },
  { x: 39, y: 64 },
  { x: 54, y: 49 },
  { x: 67, y: 37 },
  { x: 78, y: 23 },
];

function buildModules(data?: RoadmapResponse): PositionedModule[] {
  const modules = data?.gameplan_state?.modules ?? [];
  return modules.map((module, index) => ({
    id: module.id || module.title.toLowerCase().replace(/\s+/g, "-"),
    title: module.title,
    subtitle: module.goal || "",
    x: fallbackPositions[index]?.x ?? 24 + index * 10,
    y: fallbackPositions[index]?.y ?? 80 - index * 10,
    current: index === 0,
    locked: index > 2,
  }));
}

export function RoadmapPageClient() {
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [currentUserId, setCurrentUserId] = useState("");
  const [newProfileName, setNewProfileName] = useState("");
  const [roadmap, setRoadmap] = useState<RoadmapResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const userData = await fetchUsers();
        setUsers(userData.users);
        setCurrentUserId(userData.current_user_id);
        const roadmapData = await fetchRoadmap(userData.current_user_id);
        setRoadmap(roadmapData);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load roadmap");
      }
    };
    void load();
  }, []);

  const modules = buildModules(roadmap);

  const handleUserChange = async (userId: string) => {
    setCurrentUserId(userId);
    await selectUser(userId);
    const roadmapData = await fetchRoadmap(userId);
    setRoadmap(roadmapData);
  };

  const handleCreate = async () => {
    if (!newProfileName.trim()) return;
    const created = await createUser(newProfileName);
    const nextUsers = await fetchUsers();
    setUsers(nextUsers.users);
    setCurrentUserId(created.current_user_id);
    setRoadmap(await fetchRoadmap(created.current_user_id));
    setNewProfileName("");
  };

  return (
    <section className="roadmap-canvas">
      <div className="roadmap-surface">
        <div className="roadmap-topbar">
          <div className="roadmap-brand">Camino</div>
          <div className="roadmap-chips">
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
            <div className="chip">Today: {roadmap?.spaced_review_state?.todays_words?.length ?? 0} words</div>
          </div>
        </div>

        <div className="roadmap-mountain">
          <MountainGraphic />
          {modules.map((module) => {
            const nodeClass = [
              "roadmap-node",
              module.current ? "is-current" : "",
              module.locked ? "is-locked" : "",
            ]
              .filter(Boolean)
              .join(" ");

            return (
              <Link
                href={`/session/${module.id}?user=${currentUserId}`}
                key={module.id}
                className="roadmap-marker"
                style={{ left: `${module.x}%`, top: `${module.y}%` }}
              >
                <div className={nodeClass} />
                <div className="roadmap-label">
                  <strong>{module.title}</strong>
                  <span>{module.subtitle}</span>
                </div>
              </Link>
            );
          })}
          <div className="roadmap-caption">
            {error || "Click the glowing marker to begin today's session."}
          </div>
        </div>
      </div>
    </section>
  );
}
