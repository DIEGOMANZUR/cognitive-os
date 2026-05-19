"use client";

import { useMemo, useState } from "react";

import type { ApiClient } from "../lib/api";
import { errorMessage, statusClass } from "../lib/api";
import { usePolledFetch } from "../lib/hooks";
import { useToast } from "../lib/toasts";
import type {
  ActionRequestView,
  CalendarEvent,
  CalendarStatus,
  DriveFile,
  DriveFolderPreview,
  DriveOrganizePreview,
  DriveStatus,
  FreeBusyResult,
  MapsStatus,
  RoutePlan
} from "../lib/types";

type TravelMode = "driving" | "walking" | "bicycling" | "transit";
type DriveSearchMode = "name" | "full_text" | "all";
type DriveCorpus = "user" | "all_drives";

function toIso(value: string): string {
  return new Date(value).toISOString();
}

function formatBytes(value: number | null): string {
  if (value == null) return "-";
  if (value >= 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
  if (value >= 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${value} B`;
}

export function GoogleOpsView({ client }: { client: ApiClient }) {
  const authed = Boolean(client.authToken);
  const maps = usePolledFetch<MapsStatus>(client, authed ? "/actions/maps/status" : null, 30000);
  const calendar = usePolledFetch<CalendarStatus>(
    client,
    authed ? "/actions/calendar/status" : null,
    30000
  );
  const drive = usePolledFetch<DriveStatus>(client, authed ? "/actions/drive/status" : null, 30000);
  const toast = useToast();

  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [travelMode, setTravelMode] = useState<TravelMode>("driving");
  const [computeAlternatives, setComputeAlternatives] = useState(true);
  const [route, setRoute] = useState<RoutePlan | null>(null);
  const [calendarEvents, setCalendarEvents] = useState<CalendarEvent[]>([]);
  const [freeBusy, setFreeBusy] = useState<FreeBusyResult | null>(null);
  const [eventSummary, setEventSummary] = useState("");
  const [eventStart, setEventStart] = useState("");
  const [eventEnd, setEventEnd] = useState("");
  const [eventLocation, setEventLocation] = useState("");
  const [driveQuery, setDriveQuery] = useState("");
  const [driveSearchMode, setDriveSearchMode] = useState<DriveSearchMode>("all");
  const [driveCorpus, setDriveCorpus] = useState<DriveCorpus>("user");
  const [driveIncludeFolders, setDriveIncludeFolders] = useState(true);
  const [driveFiles, setDriveFiles] = useState<DriveFile[]>([]);
  const [uploadPath, setUploadPath] = useState("");
  const [uploadName, setUploadName] = useState("");
  const [folderPreview, setFolderPreview] = useState<DriveFolderPreview | null>(null);
  const [organizeTarget, setOrganizeTarget] = useState("");
  const [organizePreview, setOrganizePreview] = useState<DriveOrganizePreview | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const googleReady = useMemo(
    () =>
      [maps.data?.status, calendar.data?.status, drive.data?.status].flatMap((status) =>
        status ? [status] : []
      ),
    [maps.data, calendar.data, drive.data]
  );

  async function planRoute() {
    if (!origin.trim() || !destination.trim() || busy) return;
    setBusy("route");
    try {
      const result = await client.post<RoutePlan>("/actions/maps/route", {
        origin: origin.trim(),
        destination: destination.trim(),
        travel_mode: travelMode,
        traffic_aware: true,
        compute_alternatives: computeAlternatives
      });
      setRoute(result);
      toast.push("Ruta calculada con Google Maps.", "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(null);
    }
  }

  async function listCalendar() {
    if (busy) return;
    setBusy("calendar-list");
    try {
      const result = await client.post<CalendarEvent[]>("/actions/calendar/events", { max_results: 20 });
      setCalendarEvents(result);
      toast.push("Agenda cargada.", "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(null);
    }
  }

  async function checkFreeBusy() {
    if (busy) return;
    setBusy("calendar-freebusy");
    try {
      const result = await client.post<FreeBusyResult>("/actions/calendar/freebusy", {
        calendars: ["primary"]
      });
      setFreeBusy(result);
      toast.push("Disponibilidad cargada.", "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(null);
    }
  }

  async function requestCalendarEvent() {
    if (!eventSummary.trim() || !eventStart || !eventEnd || busy) return;
    setBusy("calendar-request");
    try {
      const request = await client.post<ActionRequestView>("/actions/calendar/events/request", {
        summary: eventSummary.trim(),
        start: toIso(eventStart),
        end: toIso(eventEnd),
        location: eventLocation.trim() || null,
        dry_run: false
      });
      toast.push(`Solicitud Calendar creada: ${request.status}.`, "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(null);
    }
  }

  async function searchDrive() {
    if (busy) return;
    setBusy("drive-search");
    try {
      const result = await client.post<DriveFile[]>("/actions/drive/files", {
        query: driveQuery.trim(),
        max_results: 30,
        search_mode: driveSearchMode,
        corpus: driveCorpus,
        include_folders: driveIncludeFolders
      });
      setDriveFiles(result);
      toast.push("Drive consultado.", "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(null);
    }
  }

  async function previewFolder() {
    if (busy) return;
    setBusy("folder-preview");
    try {
      const result = await client.post<DriveFolderPreview>("/actions/drive/folders/ensure", {
        dry_run: true
      });
      setFolderPreview(result);
      toast.push("Carpeta de entregables validada en modo preview.", "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(null);
    }
  }

  async function requestUpload() {
    if (!uploadPath.trim() || busy) return;
    setBusy("upload-request");
    try {
      const request = await client.post<ActionRequestView>("/actions/drive/files/upload/request", {
        local_path: uploadPath.trim(),
        drive_name: uploadName.trim() || null,
        use_deliverables_folder: true,
        dry_run: false
      });
      toast.push(`Solicitud Drive creada: ${request.status}.`, "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(null);
    }
  }

  async function requestFolder() {
    if (busy) return;
    setBusy("folder-request");
    try {
      const request = await client.post<ActionRequestView>("/actions/drive/folders/ensure/request", {
        dry_run: false
      });
      toast.push(`Solicitud de carpeta Drive creada: ${request.status}.`, "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(null);
    }
  }

  async function previewDriveOrganize() {
    if (busy) return;
    setBusy("drive-organize-preview");
    try {
      const result = await client.post<DriveOrganizePreview>("/actions/drive/organize/preview", {
        query: driveQuery.trim(),
        target_folder_name: organizeTarget.trim() || null,
        max_files: 30,
        search_mode: driveSearchMode,
        corpus: driveCorpus,
        dry_run: true
      });
      setOrganizePreview(result);
      toast.push(`Preview Drive: ${result.operation_count} archivo(s).`, "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(null);
    }
  }

  async function requestDriveOrganize() {
    if (busy) return;
    setBusy("drive-organize-request");
    try {
      const request = await client.post<ActionRequestView>("/actions/drive/organize/request", {
        query: driveQuery.trim(),
        target_folder_name: organizeTarget.trim() || null,
        max_files: 30,
        search_mode: driveSearchMode,
        corpus: driveCorpus,
        dry_run: false
      });
      toast.push(`Solicitud de organización Drive creada: ${request.status}.`, "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="stack">
      <section className="section">
        <div className="section-head">
          <div>
            <h2>Google Ops</h2>
            <p className="muted small">
              Maps es read-only. Calendar y Drive crean solicitudes aprobables antes de tocar Google.
            </p>
          </div>
          <div className="row">
            {googleReady.map((status, index) => (
              <span key={`${status}-${index}`} className={statusClass(status)}>
                {status}
              </span>
            ))}
          </div>
        </div>
      </section>

      <div className="grid-2">
        <section className="section stack">
          <div className="section-head">
            <h2>Maps · rutas con tráfico</h2>
            <span className={statusClass(maps.data?.status ?? "unknown")}>{maps.data?.status ?? "?"}</span>
          </div>
          {maps.data?.reason && <p className="badge warn">{maps.data.reason}</p>}
          <input value={origin} onChange={(event) => setOrigin(event.target.value)} placeholder="Origen" />
          <input value={destination} onChange={(event) => setDestination(event.target.value)} placeholder="Destino" />
          <div className="row">
            <select value={travelMode} onChange={(event) => setTravelMode(event.target.value as TravelMode)}>
              <option value="driving">Auto</option>
              <option value="walking">Caminando</option>
              <option value="bicycling">Bicicleta</option>
              <option value="transit">Transporte público</option>
            </select>
            <label className="check">
              <input
                type="checkbox"
                checked={computeAlternatives}
                onChange={(event) => setComputeAlternatives(event.target.checked)}
              />
              alternativas
            </label>
            <button className="primary" disabled={busy !== null || !origin || !destination} onClick={planRoute} type="button">
              Calcular ruta
            </button>
          </div>
          {route && (
            <div className="card soft stack">
              <h3>{route.distance_text} · {route.duration_text}</h3>
              {route.route_advice && <p>{route.route_advice}</p>}
              {route.traffic_aware && (
                <p className="muted small">
                  Tráfico: {route.traffic_severity}. Retraso estimado: {route.traffic_delay_text ?? "0 min"}.
                  {route.arrival_time ? ` Llegada aprox.: ${new Date(route.arrival_time).toLocaleTimeString()}.` : ""}
                  {route.alternative_count ? ` Alternativas: ${route.alternative_count}.` : ""}
                </p>
              )}
              <a href={route.google_maps_url} target="_blank" rel="noreferrer">
                Abrir en Google Maps
              </a>
              <ol className="small">
                {route.steps.slice(0, 8).map((step, index) => (
                  <li key={`${step.instruction}-${index}`}>{step.instruction}</li>
                ))}
              </ol>
            </div>
          )}
        </section>

        <section className="section stack">
          <div className="section-head">
            <h2>Calendar</h2>
            <span className={statusClass(calendar.data?.status ?? "unknown")}>{calendar.data?.status ?? "?"}</span>
          </div>
          {calendar.data?.reason && <p className="badge warn">{calendar.data.reason}</p>}
          {calendar.data?.missing_scopes && calendar.data.missing_scopes.length > 0 && (
            <p className="badge warn small">
              Re-autorizar: faltan {calendar.data.missing_scopes.length} scope(s) — borrá
              <code> storage/oauth/google/token.json</code> y corré
              <code> uv run python scripts/auth_google.py</code>. Scopes faltantes:
              {" "}
              {calendar.data.missing_scopes.join(", ")}.
            </p>
          )}
          <div className="row">
            <button onClick={listCalendar} disabled={busy !== null} type="button">Listar agenda</button>
            <button onClick={checkFreeBusy} disabled={busy !== null} type="button">Disponibilidad</button>
            <span className="muted small">write={String(calendar.data?.write_enabled ?? false)}</span>
          </div>
          <div className="card soft stack">
            <h3>Solicitar evento</h3>
            <input value={eventSummary} onChange={(event) => setEventSummary(event.target.value)} placeholder="Resumen" />
            <input type="datetime-local" value={eventStart} onChange={(event) => setEventStart(event.target.value)} />
            <input type="datetime-local" value={eventEnd} onChange={(event) => setEventEnd(event.target.value)} />
            <input value={eventLocation} onChange={(event) => setEventLocation(event.target.value)} placeholder="Ubicación opcional" />
            <button className="primary" disabled={busy !== null || !eventSummary || !eventStart || !eventEnd} onClick={requestCalendarEvent} type="button">
              Crear solicitud aprobable
              </button>
            </div>
          {freeBusy && (
            <div className="card soft stack">
              <h3>Free/busy</h3>
              <p className="muted small">
                {new Date(freeBusy.time_min).toLocaleString()} - {new Date(freeBusy.time_max).toLocaleString()} · ocupados: {freeBusy.busy_count}
              </p>
              {freeBusy.calendars.map((calendarItem) => (
                <div key={calendarItem.calendar_id} className="stack">
                  <strong>{calendarItem.calendar_id}</strong>
                  {calendarItem.busy.length === 0 ? (
                    <span className="muted small">Sin bloques ocupados.</span>
                  ) : (
                    <ul className="small">
                      {calendarItem.busy.slice(0, 5).map((slot) => (
                        <li key={`${slot.start}-${slot.end}`}>
                          {new Date(slot.start).toLocaleString()} - {new Date(slot.end).toLocaleString()}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          )}
          <div className="table-wrap">
            <table className="table small">
              <tbody>
                {calendarEvents.map((event) => (
                  <tr key={event.event_id}>
                    <td><strong>{event.summary}</strong></td>
                    <td>{new Date(event.start).toLocaleString()}</td>
                    <td>{event.html_link ? <a href={event.html_link} target="_blank" rel="noreferrer">Abrir</a> : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <section className="section stack">
        <div className="section-head">
          <div>
            <h2>Drive · nube de entregables</h2>
            <p className="muted small">
              Carpeta objetivo: <code>{drive.data?.deliverables_folder_name ?? "Cognitive OS Deliverables"}</code>.
            </p>
          </div>
          <span className={statusClass(drive.data?.status ?? "unknown")}>{drive.data?.status ?? "?"}</span>
        </div>
        {drive.data?.reason && <p className="badge warn">{drive.data.reason}</p>}
        {drive.data?.missing_scopes && drive.data.missing_scopes.length > 0 && (
          <p className="badge warn small">
            Re-autorizar: faltan {drive.data.missing_scopes.length} scope(s) — borrá
            <code> storage/oauth/google/token.json</code> y corré
            <code> uv run python scripts/auth_google.py</code>. Scopes faltantes:
            {" "}
            {drive.data.missing_scopes.join(", ")}.
          </p>
        )}
        <div className="grid-2">
          <div className="card soft stack">
            <h3>Buscar en todo Drive</h3>
            <div className="row">
              <input value={driveQuery} onChange={(event) => setDriveQuery(event.target.value)} placeholder="nombre contiene…" />
              <select value={driveSearchMode} onChange={(event) => setDriveSearchMode(event.target.value as DriveSearchMode)}>
                <option value="all">Nombre + contenido</option>
                <option value="name">Nombre</option>
                <option value="full_text">Contenido</option>
              </select>
              <select value={driveCorpus} onChange={(event) => setDriveCorpus(event.target.value as DriveCorpus)}>
                <option value="user">Mi unidad</option>
                <option value="all_drives">Todo Drive</option>
              </select>
              <button className="primary" onClick={searchDrive} disabled={busy !== null} type="button">Buscar</button>
            </div>
            <label className="check">
              <input
                type="checkbox"
                checked={driveIncludeFolders}
                onChange={(event) => setDriveIncludeFolders(event.target.checked)}
              />
              incluir carpetas
            </label>
            <button onClick={previewFolder} disabled={busy !== null} type="button">
              Validar carpeta de entregables
            </button>
            <button onClick={requestFolder} disabled={busy !== null} type="button">
              Crear solicitud de carpeta
            </button>
            <input
              value={organizeTarget}
              onChange={(event) => setOrganizeTarget(event.target.value)}
              placeholder="Carpeta destino opcional"
            />
            <div className="row">
              <button onClick={previewDriveOrganize} disabled={busy !== null} type="button">
                Preview organización
              </button>
              <button onClick={requestDriveOrganize} disabled={busy !== null} type="button">
                Solicitar organización
              </button>
            </div>
            {folderPreview && (
              <p className="muted small">Folder preview: {folderPreview.status} · {folderPreview.folder_name}</p>
            )}
            {organizePreview && (
              <p className="muted small">
                Organización: {organizePreview.status} · {organizePreview.operation_count} archivo(s) hacia {organizePreview.target_folder_name}
              </p>
            )}
          </div>
          <div className="card soft stack">
            <h3>Solicitar upload aprobado</h3>
            <input value={uploadPath} onChange={(event) => setUploadPath(event.target.value)} placeholder="Ruta local permitida" />
            <input value={uploadName} onChange={(event) => setUploadName(event.target.value)} placeholder="Nombre en Drive opcional" />
            <button className="primary" disabled={busy !== null || !uploadPath.trim()} onClick={requestUpload} type="button">
              Crear solicitud Drive
            </button>
            <p className="muted small">
              Límite: {formatBytes(drive.data?.upload_max_bytes ?? null)} · write={String(drive.data?.write_enabled ?? false)}.
            </p>
          </div>
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr><th>Nombre</th><th>Tipo</th><th>Tamaño</th><th>Modificado</th><th>Link</th></tr>
            </thead>
            <tbody>
              {driveFiles.map((file) => (
                <tr key={file.file_id}>
                  <td><strong>{file.name}</strong></td>
                  <td>{file.is_folder ? "folder" : file.mime_type}</td>
                  <td>{formatBytes(file.size_bytes)}</td>
                  <td>{file.modified_time ? new Date(file.modified_time).toLocaleString() : "-"}</td>
                  <td>{file.web_view_link ? <a href={file.web_view_link} target="_blank" rel="noreferrer">Abrir</a> : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
