# Cognitive OS Frontend

> **Estado actual (2026-05-23, commit `bbaaea8` — RELEASE APPROVED):** cockpit definitivo Next.js 16.2.6 +
> React 19 + TypeScript estricto, dark-only glass cockpit, 20 vistas en
> `app/views/*.tsx`, PWA instalable y API client con JWT local persistente.
> La prioridad de producto es fricción casi nula en un PC dedicado:
> `dedicated_local/full` puede operar con el perfil real del operador y
> auto-resolver aprobaciones permitidas por backend. El frontend debe
> mostrar ese modelo con claridad, sin esconder degradaciones ni errores.
>
> **Vistas:** `ChatView`, `DashboardView`, `SettingsView`,
> `ApprovalsView`, `MemoryView`, `JobsView`, `SandboxView`,
> `DocumentsView`, `DocumentAnalysisView`, `ConfigurationView`,
> `MailInboxView`, `LangSmithView`, `AgentsView`, `SkillsView`,
> `HealthView`, `AuditView`, `AssistView`, `GoogleOpsView`,
> `ResearchView` y `CodeDirectorView`.
>
> **Mail UI actual:** `Sync por worker` usa `/mail/sync/dispatch`; `Generar
> resumen 50` usa `/mail/digest/preview` con `sync_first=false`, por lo que
> trabaja sobre mensajes ya persistidos y no intenta sincronizar IMAP/OAuth
> desde el navegador. El resultado muestra resumen y respuestas sugeridas
> como texto; no crea drafts y no envía emails.
>
> **Componentes:** `Sidebar.tsx`, `TopBar.tsx`, `CommandPalette.tsx`,
> `NotificationCenter.tsx`, `PWA.tsx`, `ErrorBoundary.tsx`, `Charts.tsx`,
> `Icon.tsx` (set SVG curado de ~55 íconos Lucide-style).
>
> **Lenguaje visual:** glassmorphism oscuro de alto contraste, *dark-only*
> (sin toggle de tema claro), tipografía self-hosted Inter + JetBrains Mono
> vía `next/font/google`. Paleta dirigida por tokens en `app/globals.css`.
>
> **Capacidades Fase 82+:**
> - **Charts SVG sin dependencias** (`components/Charts.tsx`): `Sparkline`
>   por métrica, `AreaChart` con crosshair y leyenda, `BarList` para
>   ranking, `Donut` con centro tipado. Usa tokens, hereda `currentColor`.
> - **Centro de notificaciones** (`NotificationCenter.tsx`): side-panel
>   glass derecho con feed unificado de aprobaciones + jobs + auditoría;
>   tracking de "vistos" persistido en `localStorage`; handshake para
>   permisos push del SO (frontend listo; backend POST → SW `push` hook).
> - **Command palette mejorado** (`CommandPalette.tsx`): fuzzy match con
>   scoring de subsecuencia + boundary bonus, agrupación, íconos por
>   acción, recientes persistidos, footer con shortcuts. `Ctrl/Cmd+K`
>   escucha en capture phase desde `hooks.ts` para no perderse cuando el
>   foco está en campos editables.
> - **Defensive array guards** (`api.ts → asArray<T>(...)`): todas las
>   vistas usan `asArray(data).filter|map|...` en lugar de
>   `(data ?? []).filter(...)`. Si el backend devuelve forma incorrecta,
>   la vista cae a empty-state en vez de romper la `ErrorBoundary`.
> - **PWA endurecida**: manifest con 4 shortcuts (Chat/Aprobaciones/
>   Jobs/Health), íconos PNG 192/512 + maskable + SVG fallback,
>   `service worker v2026-05-20-glass-2` con offline shell, página
>   `/offline.html` con branding propio, handlers `push` y
>   `notificationclick`, soporte de deep-link `?tab=...`.
>
> **Carry-over Fase 71-74 vigente:**
> - JWT persistente en `localStorage` (`useLocalState`).
> - `SettingsView` muestra los tiles "Capacidades bloqueadas"
>   (`/system/readiness`) y "MCP servers" (`/system/mcp`).
> - `ConfigurationView` invierte la semántica de "danger" según
>   `operator_profile`.
> - `GoogleOpsView` deshabilita los botones de write cuando
>   `write_enabled=false` y muestra `missing_scopes`.
> - `HealthView` lista metadata como key=value; **18 componentes** (incluye
>   `mcp_client` y `operational_backlog`). Tiene el botón "Verificar en vivo"
>   (`POST /health/verify`) y el tile "Backlog operacional" — un componente
>   sólo `configured` se pinta en amarillo, no en verde (AUDIT-2026-B).
> - `MemoryView` muestra el estado del flag
>   `FAILURE_POSTMORTEM_AUTO_PROMOTE_ENABLED` en la sección de warnings.
> - `ChatView` muestra `tg…<sufijo>` para threads de Telegram.
>
> **QA verde vigente (commit `647f103`):**
> - `npm run lint` → 0 warnings (`--max-warnings 0`).
> - `npm run build` → Next 16.2.6 + Turbopack, 4 páginas estáticas OK.
> - `npx tsc --noEmit` → 0 errores.
> - `npx playwright test --reporter=list` → **31 passed** sin exportar
>   `COGOS_JWT` (auto-mint via `tests/e2e/_global-setup.ts` que llama
>   `POST /auth/local-token` en `dedicated_local/full`; en `strict` el
>   helper sigue exigiendo la env var manualmente con mensaje claro).
> - `bash scripts/full-qa.sh` desde la raíz del repo ejecuta build
>   frontend aislado con `NEXT_DIST_DIR=.next-qa` y limpia ese directorio
>   para no romper un `next start` vivo servido desde `.next`; gate
>   vigente: **950 passed**, 1 skipped, 28 deselected.
> - Anclajes de la suite oficial (`aria-label="JWT local"`, `URL base de la
>   API`, `Abrir menú`, `Cerrar`, "Estado global", "componentes ok", 20
>   TAB_LABELS, labels "Guardar"/"API base"/"JWT sin prefijo Bearer" en
>   `SettingsView`) intactos.
>
> El `ApiClient` normaliza tokens con prefijo `Bearer`, omite
> `Content-Type` en requests sin body y soporta `AbortSignal`. Next.js
> añade headers de seguridad; el service worker mantiene las APIs
> network-only.

Consola operativa en Next.js para usar Cognitive OS: chat, documentos, jobs,
aprobaciones, salud, memoria, skills, sandbox, mail personal, Google Ops y estado
del action plane. Corre en `:3001` (`:3000` lo ocupa OpenChamber).

## Desarrollo

```bash
npm ci          # reproducible (preferido)
npm run dev     # dev server con Turbopack
npm run lint    # eslint (--max-warnings 0)
npm run build   # build estática para producción
npm run serve   # build + next start -H 127.0.0.1 -p 3001
```

Configura `NEXT_PUBLIC_API_BASE_URL` (o ajustes en la UI) si la API no está en
`http://127.0.0.1:8000`. El JWT se persiste en `localStorage` bajo
`cogos.token` (perfil `dedicated_local`); el TopBar lo lee y lo escribe en
caliente sin recargar.

## Sistema de diseño (Fase 82)

Todo el cockpit comparte un único stylesheet de tokens en `app/globals.css`.
Reglas clave:

- **Dark-only.** El atributo `data-theme="dark"` queda fijo en `<html>` desde
  `app/layout.tsx`; el toggle anterior se retiró para mantener una sola
  pasada de pulido visual y consistencia PWA en cualquier SO.
- **Glass por capa.** Surfaces apiladas sobre un fondo ambient con blobs
  radiales; cada panel usa `backdrop-filter: blur(var(--blur))` + borde
  hairline + `inner-hi` para preservar profundidad.
- **Tipografía.** `--font-sans` = Inter, `--font-mono` = JetBrains Mono.
  Ambas self-hosted por `next/font/google` con `display: swap`, así la PWA
  arranca offline sin pedir Google Fonts.
- **Iconografía.** El componente `<Icon name="..." />` envuelve un set
  curado de ~55 SVGs Lucide-style (stroke 1.75, viewBox 24, hereda
  `currentColor`). Reemplaza los glifos Unicode anteriores. **No usar
  emojis ni glifos Unicode para íconos estructurales.**
- **Charts.** `<Sparkline />`, `<AreaChart />`, `<BarList />`, `<Donut />`
  en `components/Charts.tsx`. Pure SVG, tokens, accesibles via
  `role="img" aria-label`.
- **Sin Tailwind, sin shadcn.** Toda regla nueva debe añadirse a
  `globals.css` y consumirse vía clases utilitarias del propio repo.

## PWA

- **Manifest:** `app/manifest.ts` → `/manifest.webmanifest`.
  `display: standalone`, `display_override: [window-controls-overlay,
  standalone, minimal-ui]`, `categories: [productivity, utilities,
  developer]`, 4 shortcuts (Chat/Aprobaciones/Jobs/Health).
- **Íconos:** `/icons/icon-{192,512}.png` (primarios), `/icons/icon-
  maskable-512.png` (maskable), `/icons/icon.svg` (any-size fallback),
  `/icons/apple-touch-icon.{svg,png}`.
- **Service worker:** `/public/sw.js` v `cogos-v2026-05-20-glass-2`.
  Strategy: stale-while-revalidate para chunks estáticos; network-first
  con fallback a shell + `/offline.html` para navegaciones; network-only
  para todos los prefijos REST. Handlers nativos de `push` y
  `notificationclick` (el backend puede emitir Web Push payloads JSON con
  `title`/`body`/`tag`/`url`).
- **Página offline:** `/offline.html` (branded, glass dark, botón
  Reintentar).
- **Deep-links:** `?tab=<id>` desde shortcuts navega al view correcto y
  limpia el query string.

## Testing

`tests/e2e/` (Playwright). Ahora `playwright.config.ts` bloquea el service
worker en el modo test (`serviceWorkers: 'block'`) y deshabilita el cache
HTTP (`--disable-cache` + `Cache-Control: no-store`) para que un SW de un
build anterior no contamine el siguiente run con chunks viejos.

Comandos:

```bash
COGOS_JWT=<token> npx playwright test            # full suite
COGOS_JWT=<token> npx playwright test smoke      # one spec
```

## Defensive array guards

Todas las vistas que consumen colecciones de `usePolledFetch<T[]>`
emplean `asArray(data)` en lugar de `(data ?? [])`. El helper vive en
`app/lib/api.ts`:

```ts
export function asArray<T>(value: T[] | null | undefined): T[];
export function asArray<T = unknown>(value: unknown): T[];
export function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}
```

Si el backend responde un objeto envoltura o JSON corrupto, la vista cae
a empty-state en vez de tirar la app entera dentro del `ErrorBoundary`.
