# Cognitive OS Frontend

> **Estado actual (2026-05-15, Fase 32 hardening comercial):** Next.js 16.2.6 (Turbopack),
> React 19, ESLint 9.39.4, TypeScript 5.8. **18 vistas** confirmadas en
> `app/views/*.tsx`: `ChatView`, `DashboardView`, `SettingsView`,
> `ApprovalsView`, `MemoryView`, `JobsView`, `SandboxView`,
> `DocumentsView`, `DocumentAnalysisView`, `ConfigurationView`,
> `MailInboxView`, `LangSmithView`, `AgentsView`, `SkillsView`,
> `HealthView`, `AuditView`, `AssistView` (tareas/notas personales) y
> `GoogleOpsView` (Maps/Calendar/Drive). Componentes principales: `Sidebar.tsx`, `TopBar.tsx`,
> `CommandPalette.tsx`, `PWA.tsx`. Las respuestas **research** pueden
> combinar en backend OpenHarness + DeepAgents sin cambiar la UI (ver
> `docs/OPENHARNESS_FUSION.md`). La vista `Mail` consume `/mail/*` para
> sync GoDaddy/Gmail-label, propuestas editables y envío aprobado por SMTP
> GoDaddy con estado `pending_send` y `MailSendResult`. La vista `Assist`
> consume `/assist/tasks` y `/assist/notes` para gestionar tareas
> personales, recordatorios y notas multi-tag (incluye búsqueda vectorial
> vía `/assist/notes/search`). La vista `Google Ops` consume Maps Routes,
> Calendar y Drive con ActionRequests aprobables para writes. Next.js añade
> headers de seguridad, el service worker mantiene APIs network-only y `PWA.tsx`
> cubre install/offline/update. El `ApiClient` normaliza tokens pegados con
> prefijo `Bearer`, no envía `Content-Type: application/json` en requests
> sin body, y soporta `AbortSignal` para cancelar polls obsoletos. JWT en
> memoria de sesión React (no `localStorage`). QA: `npm run lint` 0
> warnings, `npm run build` (Next.js 16.2.6 Turbopack) verde.

Consola operativa en Next.js para usar Cognitive OS: chat, documentos, jobs,
aprobaciones, salud, memoria, skills, sandbox, mail personal, Google Ops y estado
del action plane.

## Desarrollo

```bash
npm ci          # reproducible (preferido)
npm run dev     # dev server con Turbopack
npm run lint    # eslint (--max-warnings 0)
npm run build   # build estática para producción
```

Configura `NEXT_PUBLIC_API_BASE_URL` (o ajustes en la UI) si la API no está en
`http://127.0.0.1:8000`. La consola valida JWT antes de pegar a la API.
Por seguridad, el JWT queda en estado de sesión React y no se persiste
automáticamente en `localStorage`; al recargar la página hay que pegarlo de
nuevo o implementar un flujo auth real.
