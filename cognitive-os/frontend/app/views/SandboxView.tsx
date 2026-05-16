"use client";

import { useState } from "react";

import type { ApiClient } from "../lib/api";
import { errorMessage, statusClass } from "../lib/api";
import { usePolledFetch } from "../lib/hooks";
import { useToast } from "../lib/toasts";

type OpenShellRunResponse = {
  status: string;
  job_id?: string | null;
  approval_id?: string | null;
  result?: unknown;
};

export function SandboxView({ client }: { client: ApiClient }) {
  const status = usePolledFetch<Record<string, unknown>>(client, "/sandbox/openshell/status", 8000);
  const [instruction, setInstruction] = useState("");
  const [allowNetwork, setAllowNetwork] = useState(false);
  const [busy, setBusy] = useState(false);
  const [response, setResponse] = useState<OpenShellRunResponse | null>(null);
  const toast = useToast();
  const trimmedInstruction = instruction.trim();
  const canRun = trimmedInstruction.length > 0;

  async function run() {
    const requestInstruction = instruction.trim();
    if (!requestInstruction) {
      toast.push("Ingresá una instrucción válida para ejecutar en sandbox.", "error");
      return;
    }

    setResponse(null);
    setBusy(true);
    try {
      const result = await client.post<OpenShellRunResponse>("/sandbox/openshell/run", {
        task_id: crypto.randomUUID(),
        thread_id: "manual-panel",
        user_id: null,
        purpose: "other",
        instruction: requestInstruction,
        input_files: [],
        allow_network: allowNetwork
      });
      setResponse(result);
      toast.push(`Sandbox: ${result.status}`, result.status === "queued" ? "success" : "info");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid-2">
      <section className="section stack">
        <div className="section-head">
          <h2>OpenShell sandbox</h2>
          {status.data && (
            <span className={statusClass(String(status.data.status ?? "unknown"))}>
              {String(status.data.status ?? "?")}
            </span>
          )}
        </div>
        <p className="muted small">
          Ejecutá tareas en sandbox aislado vía vendor OpenShell. Cualquier instrucción riesgosa
          dispara `human_approval` antes de correr.
        </p>
        <textarea
          placeholder="Instrucción (ej: prueba este script de extracción de fechas en una muestra)"
          value={instruction}
          onChange={(event) => setInstruction(event.target.value)}
          style={{ minHeight: 140 }}
        />
        <label className="check">
          <input
            type="checkbox"
            checked={allowNetwork}
            onChange={(event) => setAllowNetwork(event.target.checked)}
          />
          <span>Permitir red (riesgo alto, requiere aprobación)</span>
        </label>
        <button className="primary" disabled={busy || !canRun} onClick={run} type="button">
          Ejecutar tarea
        </button>
      </section>
      <section className="section stack">
        <h2>Estado del gateway</h2>
        <pre style={{ maxHeight: 320 }}>
          {status.data ? JSON.stringify(status.data, null, 2) : "Cargando…"}
        </pre>
        {response && (
          <>
            <h3>Última respuesta</h3>
            <pre>{JSON.stringify(response, null, 2)}</pre>
          </>
        )}
      </section>
    </div>
  );
}
