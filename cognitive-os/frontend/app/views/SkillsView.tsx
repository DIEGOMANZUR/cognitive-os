"use client";

import { useState } from "react";

import type { ApiClient } from "../lib/api";
import { errorMessage } from "../lib/api";
import { usePolledFetch } from "../lib/hooks";
import { useToast } from "../lib/toasts";
import type { DeepAgentSkill, SkillDetail } from "../lib/types";

export function SkillsView({ client }: { client: ApiClient }) {
  const skills = usePolledFetch<DeepAgentSkill[]>(client, "/deepagents/skills", 30000);
  const [openName, setOpenName] = useState<string | null>(null);
  const [detail, setDetail] = useState<SkillDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const toast = useToast();

  async function open(name: string) {
    if (openName === name) {
      setOpenName(null);
      setDetail(null);
      return;
    }
    setOpenName(name);
    setDetail(null);
    setLoading(true);
    try {
      const data = await client.get<SkillDetail>(`/deepagents/skills/${encodeURIComponent(name)}`);
      setDetail(data);
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="section">
      <div className="section-head">
        <h2>DeepAgents · Skills habilitadas</h2>
        <span className="muted small">{(skills.data ?? []).length} activas</span>
      </div>
      <div className="grid">
        {(skills.data ?? []).length === 0 && <p className="muted small">Sin skills cargadas.</p>}
        {(skills.data ?? []).map((skill) => {
          const expanded = openName === skill.name;
          return (
            <article
              key={skill.name}
              className="metric-card"
              style={{
                minHeight: 140,
                gridColumn: expanded ? "1 / -1" : undefined
              }}
            >
              <div className="row">
                <span className="metric-label">{skill.name}</span>
                <span className={`badge ${skill.risk_level === "high" ? "warn" : "info"}`}>
                  {skill.risk_level}
                </span>
                <span className="muted small">v{skill.version}</span>
              </div>
              <p className="small muted" style={{ margin: 0 }}>{skill.description}</p>
              <p className="small muted" style={{ margin: 0 }}>
                tools: {skill.allowed_tools.length ? skill.allowed_tools.join(", ") : "—"}
              </p>
              <div className="row">
                <button onClick={() => open(skill.name)} type="button">
                  {expanded ? "Cerrar" : "Ver SKILL.md"}
                </button>
              </div>
              {expanded && loading && <p className="muted small">Cargando…</p>}
              {expanded && detail && (
                <pre style={{ maxHeight: 480, overflow: "auto" }}>{detail.content}</pre>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
