"use client";

import { useMemo, useState } from "react";

import type { ApiClient } from "../lib/api";
import { errorMessage, statusClass } from "../lib/api";
import { usePolledFetch } from "../lib/hooks";
import { useToast } from "../lib/toasts";
import type { PersonalNote, PersonalTask, PersonalTaskStatus } from "../lib/types";

const TASK_STATUSES: Array<"" | PersonalTaskStatus> = ["", "pending", "in_progress", "done", "cancelled"];

function parseTags(value: string): string[] {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function formatDate(value: string | null): string {
  if (!value) return "-";
  return new Intl.DateTimeFormat("es", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

export function AssistView({ client }: { client: ApiClient }) {
  const [taskStatus, setTaskStatus] = useState<"" | PersonalTaskStatus>("pending");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDescription, setTaskDescription] = useState("");
  const [taskTags, setTaskTags] = useState("");
  const [taskPriority, setTaskPriority] = useState(3);
  const [noteTitle, setNoteTitle] = useState("");
  const [noteBody, setNoteBody] = useState("");
  const [noteTags, setNoteTags] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const toast = useToast();

  const taskPath = useMemo(() => {
    const params = new URLSearchParams({ limit: "120" });
    if (taskStatus) params.append("statuses", taskStatus);
    return `/assist/tasks?${params.toString()}`;
  }, [taskStatus]);

  const tasks = usePolledFetch<PersonalTask[]>(client, taskPath, 10000);
  const notes = usePolledFetch<PersonalNote[]>(client, "/assist/notes?limit=80", 12000);

  async function createTask() {
    if (!taskTitle.trim() || busy) return;
    setBusy("create-task");
    try {
      await client.post<PersonalTask>("/assist/tasks", {
        title: taskTitle.trim(),
        description: taskDescription.trim() || null,
        priority: taskPriority,
        tags: parseTags(taskTags)
      });
      setTaskTitle("");
      setTaskDescription("");
      setTaskTags("");
      setTaskPriority(3);
      toast.push("Tarea creada.", "success");
      void tasks.refetch();
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(null);
    }
  }

  async function updateTaskStatus(task: PersonalTask, status: PersonalTaskStatus) {
    if (busy) return;
    setBusy(task.id);
    try {
      await client.patch<PersonalTask>(`/assist/tasks/${task.id}`, { status });
      toast.push("Tarea actualizada.", "success");
      void tasks.refetch();
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(null);
    }
  }

  async function deleteTask(task: PersonalTask) {
    if (busy) return;
    setBusy(task.id);
    try {
      await client.delete(`/assist/tasks/${task.id}`);
      toast.push("Tarea eliminada.", "success");
      void tasks.refetch();
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(null);
    }
  }

  async function createNote() {
    if (!noteTitle.trim() || busy) return;
    setBusy("create-note");
    try {
      await client.post<PersonalNote>("/assist/notes", {
        title: noteTitle.trim(),
        body_markdown: noteBody,
        tags: parseTags(noteTags)
      });
      setNoteTitle("");
      setNoteBody("");
      setNoteTags("");
      toast.push("Nota creada.", "success");
      void notes.refetch();
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(null);
    }
  }

  async function deleteNote(note: PersonalNote) {
    if (busy) return;
    setBusy(note.id);
    try {
      await client.delete(`/assist/notes/${note.id}`);
      toast.push("Nota eliminada.", "success");
      void notes.refetch();
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="grid-2" style={{ gridTemplateColumns: "minmax(0, 1.15fr) minmax(0, 1fr)" }}>
      <section className="section">
        <div className="section-head">
          <div>
            <h2>Asistente personal</h2>
            <p className="muted small">Tareas y notas locales por usuario. Sin sincronización externa.</p>
          </div>
          <div className="row">
            <select value={taskStatus} onChange={(event) => setTaskStatus(event.target.value as "" | PersonalTaskStatus)}>
              {TASK_STATUSES.map((status) => (
                <option key={status || "all"} value={status}>
                  {status || "Todas"}
                </option>
              ))}
            </select>
            <button className="ghost" onClick={() => void tasks.refetch()} type="button">
              Refrescar
            </button>
          </div>
        </div>

        <div className="card soft stack">
          <h3>Nueva tarea</h3>
          <input value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} placeholder="Título" />
          <textarea
            rows={3}
            value={taskDescription}
            onChange={(event) => setTaskDescription(event.target.value)}
            placeholder="Descripción opcional"
          />
          <div className="row">
            <input
              value={taskTags}
              onChange={(event) => setTaskTags(event.target.value)}
              placeholder="tags separados por coma"
            />
            <select value={taskPriority} onChange={(event) => setTaskPriority(Number(event.target.value))}>
              {[1, 2, 3, 4, 5].map((priority) => (
                <option key={priority} value={priority}>
                  prioridad {priority}
                </option>
              ))}
            </select>
            <button className="primary" disabled={busy !== null || !taskTitle.trim()} onClick={createTask} type="button">
              Crear
            </button>
          </div>
        </div>

        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Estado</th>
                <th>Tarea</th>
                <th>Prioridad</th>
                <th>Actualizada</th>
                <th>Acción</th>
              </tr>
            </thead>
            <tbody>
              {(tasks.data ?? []).length === 0 && (
                <tr>
                  <td colSpan={5} className="muted">Sin tareas para este filtro.</td>
                </tr>
              )}
              {(tasks.data ?? []).map((task) => (
                <tr key={task.id}>
                  <td><span className={statusClass(task.status)}>{task.status}</span></td>
                  <td>
                    <strong>{task.title}</strong>
                    {task.description && <p className="muted small">{task.description}</p>}
                    {task.tags.length > 0 && <p className="muted small">#{task.tags.join(" #")}</p>}
                  </td>
                  <td>{task.priority}</td>
                  <td>{formatDate(task.updated_at)}</td>
                  <td>
                    <div className="row">
                      <button
                        className="ghost"
                        disabled={busy !== null || task.status === "in_progress"}
                        onClick={() => updateTaskStatus(task, "in_progress")}
                        type="button"
                      >
                        Iniciar
                      </button>
                      <button
                        disabled={busy !== null || task.status === "done"}
                        onClick={() => updateTaskStatus(task, "done")}
                        type="button"
                      >
                        Hecha
                      </button>
                      <button className="danger" disabled={busy !== null} onClick={() => deleteTask(task)} type="button">
                        Borrar
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="section">
        <div className="section-head">
          <div>
            <h2>Notas</h2>
            <p className="muted small">Markdown personal simple para capturar contexto operativo.</p>
          </div>
          <button className="ghost" onClick={() => void notes.refetch()} type="button">
            Refrescar
          </button>
        </div>

        <div className="card soft stack">
          <h3>Nueva nota</h3>
          <input value={noteTitle} onChange={(event) => setNoteTitle(event.target.value)} placeholder="Título" />
          <textarea
            rows={6}
            value={noteBody}
            onChange={(event) => setNoteBody(event.target.value)}
            placeholder="Cuerpo markdown"
          />
          <div className="row">
            <input value={noteTags} onChange={(event) => setNoteTags(event.target.value)} placeholder="tags separados por coma" />
            <button className="primary" disabled={busy !== null || !noteTitle.trim()} onClick={createNote} type="button">
              Guardar nota
            </button>
          </div>
        </div>

        <div className="stack">
          {(notes.data ?? []).length === 0 && <p className="muted">Sin notas guardadas.</p>}
          {(notes.data ?? []).map((note) => (
            <article key={note.id} className="card soft stack">
              <div className="section-head">
                <div>
                  <h3>{note.title}</h3>
                  <p className="muted small">{formatDate(note.updated_at)} · {note.tags.join(", ") || "sin tags"}</p>
                </div>
                <button className="danger" disabled={busy !== null} onClick={() => deleteNote(note)} type="button">
                  Borrar
                </button>
              </div>
              {note.body_markdown ? <pre>{note.body_markdown}</pre> : <p className="muted">Nota vacía.</p>}
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
