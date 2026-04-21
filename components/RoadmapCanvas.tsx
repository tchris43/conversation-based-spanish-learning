"use client";

import Link from "next/link";
import { roadmapModules } from "@/lib/mock-data";
import { MountainGraphic } from "./MountainGraphic";

export function RoadmapCanvas() {
  return (
    <section className="roadmap-canvas">
      <div className="roadmap-surface">
        <div className="roadmap-topbar">
          <div className="roadmap-brand">Camino</div>
          <div className="roadmap-chips">
            <div className="chip">Taylor</div>
            <div className="chip">Neighbor Spanish</div>
            <div className="chip">Today: 4 words</div>
          </div>
        </div>

        <div className="roadmap-mountain">
          <MountainGraphic />
          {roadmapModules.map((module) => {
            const nodeClass = [
              "roadmap-node",
              module.current ? "is-current" : "",
              module.locked ? "is-locked" : "",
            ]
              .filter(Boolean)
              .join(" ");

            const card = (
              <>
                <div className={nodeClass} />
                <div className="roadmap-label">
                  <strong>{module.title}</strong>
                  <span>{module.subtitle}</span>
                </div>
              </>
            );

            return module.current ? (
              <Link
                href={`/session/${module.id}`}
                key={module.id}
                className="roadmap-marker"
                style={{ left: `${module.x}%`, top: `${module.y}%` }}
              >
                {card}
              </Link>
            ) : (
              <div
                key={module.id}
                className="roadmap-marker"
                style={{ left: `${module.x}%`, top: `${module.y}%` }}
              >
                {card}
              </div>
            );
          })}
          <div className="roadmap-caption">Click the glowing marker to begin today&apos;s session.</div>
        </div>
      </div>
    </section>
  );
}
