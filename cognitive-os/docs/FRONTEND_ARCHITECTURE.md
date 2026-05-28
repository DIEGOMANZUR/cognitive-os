# Frontend Architecture — Cognitive OS Cockpit

<!-- V2_ABSOLUTE_CLOSURE_STATUS_START -->

> **Cierre V2.0 absoluto local-first (2026-05-28, Prompt 7 V2.0 — re-ejecutado).** Esta rama `codex/commercial-zero-friction-hardening` queda certificada como **APTA COMERCIAL LOCAL-FIRST** para PC dedicado. Branch inicial Prompt 1 V2.0: HEAD `935193e`. El commit final del Prompt 7 V2.0 firma los deltas P3 (F-P2-101 restore + F-P2-103 + F-P2-104 parcial + F-P2-105) y P6 (V2-EVAL-200 path policy + V2-EVAL-202 docanalysis review). Evidencia viva en `tmp/v2_07_absolute_release_closure_20260528_133000/`.
>
> **Hallazgos cerrados V2.0 (10 verificados):** F-P2-101 working tree restored · F-P2-103 (P1) drive_get_file non-ASCII → 400 (15 tests) · F-P2-104 (P2 parcial) responses={} declarado, 89 endpoints en backlog R-001 · F-P2-105 (P3) `_inspect_workers_snapshot` con `connection_or_acquire` + connection=conn (verificado live **6/6 ciclos chaos consecutivos**) · F-P2-102 (P3) demostrado FALSO POSITIVO · V2-EVAL-200 (P1) `_is_sensitive_root` bloquea `~/.ssh`, `~/.gnupg`, `credentials/`, `tokens/` (16 tests) · V2-EVAL-201 (P3) log crudo Code Director ciclo completo · V2-EVAL-202 (P3) `apply_quality_evaluation` reconcilia top-level `human_review_required` con item severity=high / needs_human_review (4 tests). V2-EVAL-001/004/005 previos del cierre V2.0 anterior siguen sosteniéndose.
>
> **Gates V2.0 medidos antes del cierre absoluto:** `bash scripts/full-qa.sh` **1269 passed, 1 skipped, 28 deselected** (ruff/format/mypy/alembic/sync_doc_counts/git-diff verdes); `bash scripts/stress-qa.sh 5` **5/5 verde × 1269 passed × 2 ciclos posteriores al último cambio**, flakiness **0%**; `cd frontend && npx playwright test` **44 passed × 2 ciclos**; `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` **8 passed**; `python3 scripts/openapi_readonly_smoke.py` **70 GET / 0 failures**; `bash scripts/verify_desktop_launchers.sh` OK; bandit severity-high 0 issues; `POST /health/verify` overall **`ok`** con `mcp_client` live `ok` 6/6 y **70 tools live**; checklist 400 puntos ejecutada (P7 V2.0). **37 tests de regresión nuevos acumulados** (15 F-P2-103 + 2 F-P2-105 + 16 V2-EVAL-200 + 4 V2-EVAL-202).
>
> **Criterio de verdad:** no se declara envío de correo, draft real ni escritura DNS. Mail queda normalizado como read-only (sync/list/classify/digest + proposed replies como texto). GoDaddy preview/dry-run. Action Plane mantiene `validate→preview→request→approve→dispatch→execute→audit` con idempotencia y reapers. Computer organize/inventory bloquean `root_path` con markers sensibles (`.ssh`, `.gnupg`, `credentials`, `secret`, `tokens`, `keychain`) además de la allow-list existente. El runtime corre en `127.0.0.1` sin exposición LAN/internet. **Cognitive OS queda certificado en este commit como APTO COMERCIAL LOCAL-FIRST para PC dedicado, con funcionamiento real activado, documentación sincronizada, dos ciclos completos verdes posteriores al último cambio, Git ordenado y sin P0/P1/P2 abiertos.**

<!-- V2_ABSOLUTE_CLOSURE_STATUS_END -->


> Documento técnico estable. Estado: **2026-05-26, HEAD `8a33475`**. Acompaña a
> `cognitive-os/frontend/README.md` (orientación rápida). El cockpit mantiene
> grado comercial local-first y suma hardening público/TestSprite web: auth por
> `#cogos_token`, API pública por host, shell sin TopBar, `data-cogos-active-tab`,
> hotkey `3 DeepAgents`, estados loading/empty/error reales y SW
> `cogos-v2026-05-26e-status-cards`.
>
> El cockpit está optimizado para el perfil de instalación actual:
> `dedicated_local/full` en un PC dedicado, con prioridad de fricción casi nula
> por sobre seguridad estricta. La UI debe facilitar operación rápida, mostrar
> degradaciones de forma explícita y respetar la excepción de mail: no drafts, no
> envíos automáticos, solo propuestas de texto salvo solicitud explícita de Diego.
>
> Gates vigentes: `npm run lint` limpio, `npm run build` limpio, `npx playwright
> test --reporter=list` con **43 passed** sin exportar `COGOS_JWT` (auto-mint via
> `_global-setup.ts`), `bash scripts/full-qa.sh` desde la raíz usando build
> aislado `NEXT_DIST_DIR=.next-qa` (**1200 passed**, 1 skipped, 28 deselected),
> `stress-qa.sh 5` **5/5 verde × 1200 passed**. TestSprite web público se prepara
> con `bash scripts/testsprite_web/deploy_and_verify.sh`; no se declara doble
> verde web sin reportes del portal.
>
> Verificación live con Chrome DevTools MCP (cierre absoluto 2026-05-25): las 20
> tabs de la SPA montan sin un solo `console.error` crítico.
>
> Ajustes acumulados:
> - `8a33475`: status rows/cards comerciales para empty/loading/error y handoff
>   público TestSprite web con marker `cogos-v2026-05-26e-status-cards`.
> - `647f103`: Playwright runner zero-friction (auto-mint JWT); fix
>   `eager_defaults=True` en `db.Base` para action plane.
> - `5953b40`: `Ctrl/Cmd+K` capture phase para abrir de forma estable
>   incluso cuando el foco está dentro de un input.

Este documento describe **cómo está construido el cockpit** y **qué
reglas firmes hay que respetar** para mantenerlo en grado comercial. Si
sos un dev / agente que va a tocar el frontend por primera vez, leer
esta doc antes de tirar código ahorra tiempo y previene regresiones.

## 1. Stack y postura

- **Next.js 16.2.6** (App Router exclusivamente, sin `pages/`).
- **React 19** (`useActionState`, `use(promise)`, `useFormStatus`).
- **TypeScript 5.8** estricto (`noImplicitAny`, `strictNullChecks`).
- **ESLint 9** + `eslint-config-next`. Política: `--max-warnings 0`.
- **CSS hand-rolled con tokens** en `app/globals.css`. Una sola hoja
  compartida por todas las vistas. **Sin Tailwind, sin shadcn/ui, sin
  MUI, sin styled-components, sin emotion**.
- **Tipografía self-hosted** vía `next/font/google` (Inter +
  JetBrains Mono). Bundleada en build; la PWA arranca offline sin pedir
  Google Fonts.
- **Playwright** para E2E.

**Regla no negociable:** el repo eligió este stack deliberadamente; la
consistencia es el brief. No introducir frameworks ni librerías de
estilos paralelas. Cualquier regla nueva se añade a `globals.css` y se
consume via clases utilitarias del propio repo.

## 2. Estructura de directorios

```
app/
├── components/         Componentes shareable cross-view
│   ├── Charts.tsx        Sparkline/AreaChart/BarList/Donut (SVG puro)
│   ├── CommandPalette.tsx
│   ├── ErrorBoundary.tsx (client-side)
│   ├── Icon.tsx          Set SVG curado (~55 íconos)
│   ├── NotificationCenter.tsx
│   ├── PWA.tsx           Install / update / offline prompt
│   ├── Sidebar.tsx       Nav lateral con secciones plegables
│   ├── StatePrimitives.tsx  Skeleton/EmptyState/ErrorPanel/DataBoundary
├── lib/
│   ├── a11y.ts           useFocusTrap, helpers de accesibilidad
│   ├── api.ts            ApiClient, asArray<T>, statusClass, etc.
│   ├── hooks.ts          usePolledFetch (resiliente), useLocalState,
│   │                     useKeyboard, useHydrated, useOnline
│   ├── markdown.ts       renderMarkdownLite (chat replies)
│   ├── toasts.tsx        ToastProvider + useToast (iconificados, a11y)
│   └── types.ts          Todos los tipos compartidos con el backend
├── views/                20 vistas, una por ruta lógica del cockpit
│   └── *View.tsx
├── globals.css           Sistema de diseño (tokens, primitivas, util)
├── layout.tsx            Root layout, data-theme=dark, fonts, metadata
├── manifest.ts           PWA manifest (4 shortcuts, íconos)
└── page.tsx              App shell (sidebar+main+palette+notif+PWA)

public/
├── icons/                Set de íconos: SVG + PNG (192/512/maskable)
├── offline.html          Página de fallback offline branded
└── sw.js                 Service worker
```

## 3. Sistema de diseño

### Tokens (en `globals.css`)

Toda regla nueva consume tokens; nada se hardcodea. Los grupos:

| Grupo | Variables | Para qué |
|-------|-----------|----------|
| Surfaces base | `--bg-deep`, `--bg-base`, `--bg-elev`, `--bg-elev-2` | Fondos sólidos en capas |
| Glass surfaces | `--glass-1..3`, `--glass-hi`, `--glass-border(-hi)` | Paneles translúcidos sobre el backdrop |
| Hairlines | `--line`, `--line-strong` | Bordes finos |
| Texto | `--text`, `--text-muted`, `--text-faint` | Jerarquía tipográfica |
| Acento primario | `--accent`, `--accent-strong`, `--accent-deep`, `--accent-ink`, `--accent-soft`, `--accent-glow` | CTAs, estado activo, glow |
| Acento secundario | `--iris`, `--iris-soft` | Charts, depth |
| Status | `--ok`, `--warn`, `--danger`, `--info` (+ `-soft` cada uno) | Badges, dots, alerts |
| Radius | `--radius-xs..xl`, `--radius-pill` | Esquinas |
| Elevación | `--shadow-1..3`, `--shadow-pop`, `--inner-hi` | Profundidad |
| Motion | `--ease`, `--ease-out`, `--fast`, `--med`, `--slow` | Transiciones |
| Z-index | `--z-bottom-nav`, `--z-drawer`, `--z-toast`, `--z-palette` | Capas |

### Reglas firmes

1. **Dark-only.** `<html data-theme="dark">` queda fijo en
   `app/layout.tsx`. No reintroducir un toggle claro/oscuro sin alinear
   primero el branding y la doc.
2. **No emojis ni glifos Unicode** para íconos estructurales. Siempre
   `<Icon name="…" />`. Si falta un ícono, agregarlo a `app/components/Icon.tsx`.
3. **No inline styles** salvo para valores genuinamente dinámicos
   (`width: ${pct}%`). El resto va a `globals.css`.
4. **Iconografía consistente:** stroke 1.75, viewBox 24, hereda
   `currentColor`. Tamaño explícito (`size` prop) según rol: 13–15 en
   botones small, 17–18 en header contextual/empty-state, 21+ en hero/brand.
5. **Charts:** primitivos SVG en `components/Charts.tsx`. No instalar
   librerías de charts (Chart.js, Recharts, etc.). Si necesitás un tipo
   nuevo, agregalo siguiendo el patrón (puro SVG, themable, accesible).

## 4. Patterns clave

### 4.1 Polling resiliente con `usePolledFetch`

```ts
const jobs = usePolledFetch<JobResponse[]>(client, token ? "/jobs" : null, 5000);
// jobs.data | jobs.error | jobs.loading | jobs.refetch()
```

- **Pausa offline:** mientras `navigator.onLine === false` no golpea la
  API; el dato cacheado permanece visible y `error` muestra "Sin
  conexión — usando datos en caché". Al volver online, refetch
  inmediato.
- **Pausa visibility:** mientras `document.visibilityState !== "visible"`
  el intervalo se detiene (ahorra batería, evita ghost errors). Al
  volver visible, refetch inmediato.
- **`loading`:** `true` solo durante la primera carga (mientras `data
  == null`). Permite skeletons sin flash en cada poll.

### 4.2 Defensive list guards con `asArray<T>`

```ts
import { asArray } from "../lib/api";
const items = asArray<JobResponse>(jobs.data).filter((j) => j.status === "running");
```

**Por qué.** Si el backend responde forma incorrecta (objeto envoltura
de error, JSON malformado), `.filter()` reventaría y la vista entera
caería al `ErrorBoundary` global. `asArray` devuelve `[]` ante cualquier
forma que no sea array.

**Regla:** toda lista (`view.data ?? []`) debe migrar a
`asArray(view.data)`. El helper vive en `app/lib/api.ts`.

### 4.3 Loading / Empty / Error con `StatePrimitives`

```tsx
import { Skeleton, EmptyState, ErrorPanel, DataBoundary } from "../components/StatePrimitives";

// uso manual
{view.error && list.length === 0 && (
  <ErrorPanel error={view.error} onRetry={() => void view.refetch()} />
)}
{view.loading && list.length === 0 && !view.error && <Skeleton rows={4} />}
{!view.loading && !view.error && list.length === 0 && (
  <EmptyState icon="inbox" title="Sin datos" message="…" />
)}

// uso con boundary
<DataBoundary
  state={view}
  empty={{ icon: "jobs", title: "Sin jobs" }}
  isEmpty={(data) => data.length === 0}
>
  {(data) => <Table rows={data} />}
</DataBoundary>
```

### 4.4 Accesibilidad

- `useFocusTrap(ref, active)` en `lib/a11y.ts`. Aplicar a todo
  componente con rol `dialog`/`alertdialog` (palette, notification
  center, futuras modales).
- Cada modal debe: `role="dialog"`, `aria-modal="true"`,
  `aria-label="…"` y `tabIndex={-1}` en el contenedor focuseable.
- Escape cierra todo modal.
- Skip-link al main: `<a href="#cogos-main" class="skip-link">`. Ya está
  en `app/page.tsx`; el `<section className="main" id="cogos-main">`
  debe llevar `tabIndex={-1}` para recibir el foco al activarse.

### 4.5 PWA

- Manifest: `app/manifest.ts`. 4 shortcuts; íconos PNG 192/512 +
  maskable + SVG fallback.
- Service worker: `public/sw.js`. Versionado en el constante
  `CACHE_VERSION` (formato `cogos-v<YYYY-MM-DD>-<tag>`). **Bumpear** el
  tag al cambiar la estrategia o la lista de assets cacheados. Strategy:
  - Shell / assets estáticos / `/_next/static/`: stale-while-revalidate.
  - Navegaciones: network-first → fallback cached shell → `/offline.html`.
  - Backend (cualquier prefijo en `NETWORK_ONLY_PREFIXES`): network-only.
- Handlers nativos de `push` y `notificationclick` ya están listos. El
  backend puede emitir Web Push payloads JSON con
  `{ title, body, tag, url, requireInteraction }`. Falta wiring de
  VAPID en el backend (no bloqueante).
- Deep-links: `?tab=<id>` desde shortcuts navega al view correcto y
  limpia el query string.

## 5. RSC vs Client

Next 16 App Router → por defecto **Server Component**. Las vistas son
todas `"use client"` (necesitan hooks + interactividad). Los
componentes que viven en `components/` también son client. `page.tsx`
es client (provider de toasts, palette, etc.). `layout.tsx` y
`manifest.ts` son server (sin hooks ni browser APIs).

**Regla:** empujar `"use client"` lo más adentro posible. Si una vista
nueva pudiera ser server-rendered (read-only de datos públicos),
considerarlo antes de marcarla client.

## 6. Testing E2E (Playwright)

- Specs en `tests/e2e/`. Helper canónico en `_helpers.ts`
  (`readJwt`, `seedAuth`, `tabButton`, `watchPageHealth`,
  `filterUnexpectedErrors`, `TAB_LABELS`).
- `playwright.config.ts` aplica al global `use`:
  - `serviceWorkers: 'block'` — sin SW persistente entre runs.
  - `launchOptions.args: ['--disable-application-cache', '--disable-cache']`.
  - `extraHTTPHeaders.Cache-Control: 'no-store'`.
- **Anclajes E2E sagrados** (no cambiar sin actualizar tests):
  - `<main data-cogos-active-tab="...">` refleja la tab activa.
  - `#cogos_token=<JWT>` en el hash se persiste como `localStorage.cogos.token` y se limpia de la URL.
  - `aria-label="Abrir menú"` en hamburger mobile.
  - `aria-label="Cerrar"` en cierre de drawer y de notification panel.
  - Literales `"Estado global"` y `"componentes ok"` en Dashboard.
  - Los 20 `TAB_LABELS` declarados en `_helpers.ts`.
  - Labels `Guardar` / `API base` / `JWT sin prefijo Bearer` en
    `SettingsView`.

## 7. Performance

- `next/image` para raster, con `width`/`height` explícitos (CLS).
- `next/link` para nav interna. La nav del cockpit es state-based
  (no URLs), así que `<Link>` no aplica intra-cockpit; sí para links
  externos (LangSmith dashboard, etc).
- `next/font` para fuentes (ya self-hosted).
- Polling: pausado offline + tab hidden (ver §4.1).
- `useMemo` para listas derivadas grandes (`asArray + filter + sort`).
- Charts: SVG; performance OK hasta cientos de puntos. Para series
  >1k considerar canvas o downsampling — todavía no se necesita.

## 8. Seguridad

- Headers en `next.config.mjs`: `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`,
  `Cross-Origin-Opener-Policy: same-origin`, `Permissions-Policy`
  desactivando camera/microphone/geolocation/payment/usb.
- JWT en `localStorage` bajo `cogos.token`. Riesgo XSS asumido como
  aceptable en un cockpit local single-operator sin third-party
  scripts (per `AGENT_SELF.md` + `USER_GUIDE.md`).
- El SW solo cachea same-origin. Las APIs (otro origin típicamente)
  son siempre network-only.

## 9. Cómo añadir una vista nueva

1. Crear `app/views/MiNuevaView.tsx`. Empezar con `"use client"`.
2. Importar `usePolledFetch`, `asArray`, `Icon`, `Skeleton`,
   `EmptyState`, `ErrorPanel` según necesite.
3. Estructurar el render como:
   - Page header con `h1` + status badge.
   - Section(s) con `className="section"` (glass card).
   - Manejo de los 3 estados (loading/error/empty) consistente con §4.3.
4. Si la vista necesita un nuevo ícono → agregarlo a `Icon.tsx`.
5. Si necesita un nuevo chart → agregarlo a `Charts.tsx`.
6. Si necesita un nuevo token → agregarlo a `globals.css`.
7. Registrar la vista en:
   - `app/lib/types.ts → Tab` union.
   - `app/components/Sidebar.tsx → SECTIONS` con label + ícono.
   - `app/page.tsx` con el render condicional `{tab === "miNueva" && <MiNuevaView />}`.
   - `tests/e2e/_helpers.ts → TAB_LABELS` (añadir el label exacto).
8. Si la vista tiene interacción no trivial → escribir spec Playwright.
9. `npm run lint` (cero warnings), `npx tsc --noEmit`, `npm run build`
   antes de PR.

## 10. Anti-patrones (NO hacer)

| Anti-pattern | Por qué | Hacer en su lugar |
|---|---|---|
| `import 'tailwindcss'` o cualquier styling lib | Rompe el brief del repo | Usar tokens + clases utilitarias de `globals.css` |
| Emoji `🚀` o glifos Unicode `▸` para íconos | Inconsistente cross-OS, no themable | `<Icon name="zap" />` |
| `(x.data ?? []).filter(...)` | Si el backend envía objeto, `.filter` rompe la SPA | `asArray(x.data).filter(...)` |
| `<div onClick=...>` para acción | A11y rota | `<button type="button" onClick=...>` |
| Hardcoded `"#5fe3cf"` en un componente | Rompe el design system | `var(--accent)` |
| Toggle de tema claro | Decisión Fase 82 | Mantener dark-only |
| Modal sin focus trap | Tab "escapa" detrás del modal | `useFocusTrap(ref, open)` |
| `useEffect` para fetch de datos que pueden cargarse server-side | Hidratación lenta, FOUC | Server Component + `fetch` con `revalidate` |
| Service worker sin bumpear `CACHE_VERSION` | Browsers retienen cache vieja | Bumpear el sufijo del const |

## 11. Checklist pre-PR

- [ ] `npm run lint` → 0 warnings (`--max-warnings 0`).
- [ ] `npx tsc --noEmit` → 0 errores.
- [ ] `npm run build` → verde.
- [ ] Cada vista tocada renderiza sus 3 estados (loading / error / empty).
- [ ] Cualquier modal nuevo tiene `useFocusTrap`, `role="dialog"`,
      `aria-modal="true"`, `aria-label`, ESC para cerrar.
- [ ] Sin emojis ni glifos Unicode introducidos como íconos.
- [ ] Tokens nuevos (si se añadieron) documentados aquí en §3.
- [ ] `CACHE_VERSION` del SW bumpeado si cambian assets cacheados.
- [ ] Spec Playwright si la feature tiene interacción no cubierta.
- [ ] `cognitive-os/progress.md` actualizado con la entrada del cambio.

## 12. Referencias rápidas

- `frontend/README.md` — orientación rápida para devs.
- `progress.md` — bitácora viva del proyecto.
- `AGENTS.md` (raíz del workspace) §"Reglas firmes para futuras
  intervenciones en el frontend" — política para futuros agentes.
- `docs/USER_GUIDE.md` — guía pública del producto.
- `docs/SECURITY.md` — postura de seguridad.
