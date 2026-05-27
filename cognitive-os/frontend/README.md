# Cognitive OS Frontend

<!-- V2_ABSOLUTE_CLOSURE_STATUS_START -->

> **Cierre V2.0 absoluto local-first (2026-05-27, Prompt 7):** esta rama `codex/commercial-zero-friction-hardening` en base `8a33475d0502` queda sincronizada para el cierre comercial local-first. La evidencia viva se concentra en `/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/tmp/v2_07_absolute_release_closure_20260527_050231`. Estado de producto verificado durante Prompt 7: backend FastAPI local, frontend Next.js, Docker services, Postgres, Redis, Weaviate, Neo4j, Alembic head, worker, beat, health/readiness, LangGraph/chat, DeepAgents, MCP, RAG/documentos, Document Analysis, Action Plane sandbox, mail read-only, Telegram, Google read-only, GoDaddy dry-run, Kimi WebBridge y Code Director toy/guard rails.
>
> **Gates V2.0 ejecutados antes de los dos ciclos verdes finales:** `bash scripts/full-qa.sh` **1221 passed, 1 skipped, 28 deselected**; `bash scripts/stress-qa.sh 5` **5/5 verde x 1221 passed**; `cd frontend && npx playwright test` **44 passed**; `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` **8 passed**; `python3 scripts/sync_doc_counts.py --check` OK; `bash scripts/verify_desktop_launchers.sh` OK; OpenAPI read-only smoke **70 GET / 0 failures**; security read-only scan sin secretos críticos; CDP/Playwright forense **10 ciclos x 20 vistas** sin console/page errors ni 5xx, con un aborto `POST /auth/local-token` adjudicado como cierre de contexto del harness y no defecto de producto; Lighthouse local: accessibility 96, best-practices 100, SEO 100.
>
> **Criterio de verdad:** no se declara envio de correo, draft real ni escritura DNS. Mail queda normalizado como read-only: sync/list/classify/digest/proposed replies como texto, sin drafts ni sends. GoDaddy queda preview/dry-run; Action Plane mantiene sandbox/approval/audit/idempotencia segun riesgo. El tunnel publico `cognitive.doctormanzur.com` se valida con `scripts/testsprite_web/deploy_and_verify.sh` cuando Diego vaya a correr TestSprite web; Prompt 7 no lo expone permanentemente porque su propia regla prohibe exponer servicios a internet.

<!-- V2_ABSOLUTE_CLOSURE_STATUS_END -->


> **Estado actual (2026-05-26, HEAD `8a33475`):** cockpit definitivo Next.js 16.2.6 +
> React 19 + TypeScript estricto, dark-only glass cockpit, 20 vistas en
> `app/views/*.tsx`, PWA instalable y API client con JWT persistente. La
> prioridad sigue siendo fricción casi nula en un PC dedicado
> (`dedicated_local/full`), pero el frontend debe mostrar estados reales y
> auditables: nada de datos falsos, loaders infinitos ni éxito silencioso.
>
> **Hardening frontend/TestSprite web 2026-05-26:** el flujo público usa
> `https://cognitive.doctormanzur.com` + API
> `https://cognitive-api.doctormanzur.com`; `app/lib/apiBase.ts` resuelve
> automáticamente el backend correcto por host, acepta `#cogos_token=...`,
> persiste `localStorage.cogos.token` y limpia el fragmento de la URL. El
> TopBar fue retirado: el shell estable vive en sidebar + header contextual +
> `data-cogos-active-tab` sobre `<main>`.
>
> **Vistas:** `ChatView`, `DashboardView`, `SettingsView`,
> `ApprovalsView`, `MemoryView`, `JobsView`, `SandboxView`,
> `DocumentsView`, `DocumentAnalysisView`, `ConfigurationView`,
> `MailInboxView`, `LangSmithView`, `AgentsView`, `SkillsView`,
> `HealthView`, `AuditView`, `AssistView`, `GoogleOpsView`,
> `ResearchView` y `CodeDirectorView`.
>
> **Navegación vigente:** hotkeys `1 Dashboard`, `2 Chat`, `3 DeepAgents`,
> `4 Document Analysis`, `5 Jobs`, `6 Aprobaciones`, `7 LangSmith`,
> `8 Audit`, `9 Health`. `Ctrl/Cmd+K` escucha en capture phase; las acciones
> `Ir a ...` mantienen la paleta abierta para saltos rápidos y las acciones
> one-shot la cierran. Las hotkeys numéricas se leen desde `key`, `code`
> (`DigitN`/`NumpadN`) y `keyCode`, y se ignoran dentro de campos editables.
>
> **Estados comerciales:** `DocumentsView` conserva tabla/header y muestra
> filas de estado reales para loading/empty/error; `AgentsView` conserva cards
> reales mediante `AgentsStatusCard`; `AuditView`/`HealthView` usan paneles de
> error/skeleton/empty-state; `MailInboxView` mantiene el panel de propuesta
> estable sin habilitar envío ni drafts. Estos son arreglos de producto, no
> placeholders para TestSprite.
>
> **Responsive:** breakpoint comercial `920px`; en móvil el sidebar se desmonta
> salvo drawer abierto y aparece bottom nav. La sincronización usa `matchMedia`,
> `orientationchange` y `visualViewport`, sin scripts inline ni observers de
> emergencia.
>
> **Componentes:** `Sidebar.tsx`, `CommandPalette.tsx`,
> `NotificationCenter.tsx`, `PWA.tsx`, `ErrorBoundary.tsx`, `Charts.tsx`,
> `Icon.tsx` (set SVG curado de ~55 íconos Lucide-style).
>
> **Lenguaje visual:** glassmorphism oscuro de alto contraste, *dark-only*
> (sin toggle de tema claro), tipografía self-hosted Inter + JetBrains Mono
> vía `next/font/google`. Paleta dirigida por tokens en `app/globals.css`.
>
> **PWA vigente:** manifest con 4 shortcuts (Chat/Aprobaciones/Jobs/Health),
> íconos PNG/SVG/maskable, `/offline.html`, handlers `push` y
> `notificationclick`, deep-link `?tab=...`, APIs network-only y service worker
> `cogos-v2026-05-26e-status-cards`.
>
> **QA/deploy vigente:** `bash scripts/testsprite_web/deploy_and_verify.sh`
> es el único comando de despliegue público para re-runs web: reconstruye el
> frontend, levanta backend/worker/beat/frontend/tunnel, espera HTTP 200,
> valida `/health`, verifica el marker del service worker y confirma que la raíz
> sirve la cockpit shell. La última reparación quedó lista para rerun humano en
> TestSprite web; no declarar dos corridas web verdes hasta recibir esos PDFs.
>
> El `ApiClient` normaliza tokens con prefijo `Bearer`, omite `Content-Type` en
> requests sin body, soporta `AbortSignal` y sanea respuestas HTML/404 de una API
> mal apuntada. Next.js añade headers de seguridad; el service worker mantiene
> los prefijos REST en network-only.

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
`cogos.token` (perfil `dedicated_local`); se autoprovisiona o se configura en
`Conexión` para no ocupar espacio permanente en la pantalla principal.

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
- **Service worker:** `/public/sw.js` v `cogos-v2026-05-26e-status-cards`.
  Strategy: stale-while-revalidate para chunks estáticos; network-first
  con fallback a shell + `/offline.html` para navegaciones; network-only
  para todos los prefijos REST. Este marker es el cache-bust canónico que
  `scripts/testsprite_web/deploy_and_verify.sh` valida en `/sw.js` antes de
  autorizar un rerun web. Handlers nativos de `push` y `notificationclick`
  (el backend puede emitir Web Push payloads JSON con `title`/`body`/`tag`/`url`).
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
npx playwright test            # full suite; globalSetup auto-mintea JWT en dedicated_local/full
npx playwright test smoke      # spec acotado
```

Para publicar la build actual en los dominios de TestSprite web, usar desde la
raíz del repo:

```bash
bash scripts/testsprite_web/deploy_and_verify.sh
```

Ese script reconstruye producción, levanta el túnel Cloudflare, espera HTTP 200
y valida `cogos-v2026-05-26e-status-cards` en `/sw.js`.

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
