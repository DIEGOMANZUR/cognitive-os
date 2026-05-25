# Guía de Credenciales — paso a paso, con detalle de cada botón

> **Estado actual (2026-05-23, commit `bbaaea8` — RELEASE APPROVED):** esta guía sigue siendo la referencia de
> credenciales, pero el modelo operativo cambió: Cognitive OS corre en un
> PC dedicado y prioriza fricción casi nula por sobre seguridad estricta.
> Eso significa que se permite usar el perfil real del operador, Edge real
> y credenciales locales persistidas cuando Diego lo decida. La excepción
> dura es mail: las credenciales de Gmail/GoDaddy habilitan lectura y
> digest; no habilitan envío automático en el flujo normal.
>
> Guía operativa para obtener **cada credencial** que Cognitive OS puede
> usar. Pensada para que la sigas sin saber nada previo: te digo a qué
> web entrar, qué botón apretar, cómo se llama, dónde está y de qué
> color es, hasta tener el valor en la mano y pegarlo en `.env`.

## Cómo leer esta guía

- **Aviso honesto sobre las webs de los proveedores:** Google, GitHub,
  GoDaddy, etc. **cambian su interfaz seguido** (rebrands, tests A/B,
  idioma según tu país). Describo los botones tal como están hoy con su
  color y ubicación habitual, pero si un botón cambió de color o de
  texto, **buscá la *función* que describo** (“crear API key”, “nuevo
  token”) — esa no cambia aunque el píxel sí. Cuando un nombre puede
  variar, te doy también el nombre alternativo.
- **Colores:** los describo como referencia visual. Si tu navegador
  está en modo oscuro o el proveedor cambió el tema, el color puede
  diferir; fiate del **texto del botón** primero, del color después.
- **Dónde pegar cada valor:** al final de cada credencial te digo la
  línea exacta de `.env` (archivo `cognitive-os/.env`). Nunca subas ese
  archivo a git.

## Estado actual en esta máquina (2026-05-22)

Verificá en cualquier momento con:

```bash
cd cognitive-os
bash scripts/init_credentials.sh
```

**Todo lo crítico está configurado y verificado en vivo:**

- ✅ Telegram — bot `@Socio_dimn_bot`, `TELEGRAM_ENABLED=true`, user
  autorizado. Acepta slash commands + mensajes conversacionales.
- ✅ Google Calendar/Drive — OAuth corrido (`scripts/auth_google.py`),
  componentes `ready`. `GOOGLE_CALENDAR_SCOPES` usa el scope completo
  `https://www.googleapis.com/auth/calendar` (cubre eventos **y** free/busy;
  el scope `calendar.events` por sí solo daba `403` en `freeBusy`).
- ✅ Gmail — OAuth corrido (`scripts/auth_gmail.py`), lectura de
  `TODOS` + `SPAM` para `diegomanzurn@gmail.com`.
- ✅ GoDaddy mail — lectura de carpeta `Spam` para
  `diego@doctormanzur.com`; SMTP solo como escape hatch explícito.
- ✅ GoDaddy DNS producción — auth HTTP 200, modo seguro dry-run.
- ✅ MCP — 6 servidores conectados (Supermemory, GitHub, filesystem,
  Claude Code, Gemini CLI y time local), **69 tools**. Verificable en
  `/system/mcp`; `time` no requiere credencial.
- ✅ LLM gateway (gpt-5.5 / gemini-3.1-pro-low / glm-4.6v), embeddings,
  ElevenLabs, CapSolver, LangSmith.

La PARTE A de abajo describe cómo obtener cada credencial **por si
necesitás rotarla o rehacerla**. La PARTE B documenta las demás. Para el
cliente MCP, las credenciales (token de Supermemory, PAT de GitHub) van
en la línea `MCP_SERVERS` de `.env` como headers
`header_Authorization=Bearer <token>` — ver `docs/COGNITIVE_OS_GUIDE.md`
sección MCP.

---

# PARTE A — Las 6 pendientes (prioridad)

---

## A.1 · ACTION_PAYLOAD_ENCRYPTION_KEY (no necesita web)

**Qué habilita:** cifrado at-rest del `payload_executable` de las
acciones. **Obligatorio en producción** (`ENVIRONMENT=production` no
arranca sin esto).

**No hay web.** Se genera con un comando local. **Importante:** usá la
**ruta absoluta entre comillas** (la ruta del proyecto tiene un espacio
en “PROYECTO COGNITIVE OS”; sin comillas el `cd` falla y entonces
`python` corre fuera del entorno y tira
`ModuleNotFoundError: No module named 'cryptography'`):

```bash
cd "/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os/backend" && uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

- El `cd ... &&` encadenado garantiza que el `python` solo corre si el
  `cd` tuvo éxito.
- Tiene que ser **`uv run python`** (no `python` a secas): `uv` activa
  el venv del backend, que es donde está instalado `cryptography`.

Vas a obtener una cadena de 44 caracteres que termina en `=`
(p. ej. `QVsZ8YE0...MpoMU=`).

**Dónde pegarlo** — en `cognitive-os/.env`:

```
ACTION_PAYLOAD_ENCRYPTION_KEY=<la cadena que imprimió el comando>
ACTION_PAYLOAD_ENCRYPTION_REQUIRED=true     # ponelo en true si vas a producción
```

> Guardá esa key fuera del repo también (gestor de contraseñas). Si la
> perdés, los payloads cifrados ya guardados no se pueden descifrar.

---

## A.2 · GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET (Google Cloud Console)

**Qué habilita:** el digest de Gmail solo-lectura (`/gmaildigest` en
Telegram, vista *Mail*).

> Nota: podés **reutilizar el mismo cliente OAuth** que ya usás para
> Google Calendar/Drive (`GOOGLE_CLIENT_ID/SECRET`). Si querés uno
> separado solo para Gmail, seguí estos pasos; si no, copiá los valores
> de Google y saltá a “Dónde pegarlo”.

### Paso 1 — Entrar a Google Cloud Console

1. Abrí el navegador y andá a **https://console.cloud.google.com**.
2. Iniciá sesión con tu cuenta de Google (la del Gmail que vas a leer).
3. Arriba a la izquierda, al lado del logo **“Google Cloud”**, hay un
   **selector de proyecto** (un botón gris/blanco con el nombre del
   proyecto o “Selecciona un proyecto”). Hacé click.
4. En el popup, arriba a la derecha, botón **“PROYECTO NUEVO”** (texto
   azul). Click.
5. Campo **“Nombre del proyecto”**: escribí `cognitive-os`. Botón
   **“CREAR”** (botón azul, abajo). Esperá ~10s a que se cree y
   seleccionalo en el mismo selector de proyecto.

### Paso 2 — Habilitar la Gmail API

1. Menú hamburguesa **☰** (arriba a la izquierda, tres líneas
   horizontales) → **“APIs y servicios”** → **“Biblioteca”**.
2. En la barra de búsqueda central escribí `Gmail API` y apretá Enter.
3. Click en la tarjeta **“Gmail API”** (ícono de sobre rojo/blanco).
4. Botón azul grande **“HABILITAR”** (“ENABLE”). Click. Espera unos
   segundos.

### Paso 3 — Configurar la pantalla de consentimiento OAuth

1. Menú **☰** → **“APIs y servicios”** → **“Pantalla de consentimiento
   de OAuth”** (“OAuth consent screen”).
2. Tipo de usuario: elegí **“Externo”** (radio button). Botón **“CREAR”**
   (azul).
3. **Nombre de la aplicación:** `Cognitive OS`. **Correo de asistencia
   del usuario:** tu email (se autocompleta en el desplegable).
   **Datos de contacto del desarrollador:** tu email otra vez.
4. Botón **“GUARDAR Y CONTINUAR”** (azul, abajo) en cada una de las
   pantallas siguientes (Permisos, Usuarios de prueba) sin agregar nada.
5. En **“Usuarios de prueba”** → botón **“+ ADD USERS”** → escribí **tu
   propio email** → **“GUARDAR Y CONTINUAR”**. (Esto te permite usar la
   app en modo prueba sin verificación de Google.)

### Paso 4 — Crear las credenciales OAuth (Desktop)

1. Menú **☰** → **“APIs y servicios”** → **“Credenciales”**
   (“Credentials”).
2. Arriba, botón **“+ CREAR CREDENCIALES”** (texto azul con un “+”).
   Click → del desplegable elegí **“ID de cliente de OAuth”** (“OAuth
   client ID”).
3. **Tipo de aplicación:** desplegable → elegí **“Aplicación de
   escritorio”** (“Desktop app”). **Es importante que sea Desktop**, no
   Web.
4. **Nombre:** `cognitive-os-desktop`. Botón **“CREAR”** (azul).
5. Aparece un popup **“Cliente de OAuth creado”** con dos cajas:
   - **Tu ID de cliente** (`...apps.googleusercontent.com`)
   - **Tu secreto de cliente** (`GOCSPX-...`)
   Hay un ícono de **copiar** (dos cuadraditos superpuestos) al lado de
   cada uno. Copialos. También podés bajar el JSON con el botón
   **“DESCARGAR JSON”**.

**Dónde pegarlo** — en `cognitive-os/.env`:

```
GMAIL_CLIENT_ID=<...apps.googleusercontent.com>
GMAIL_CLIENT_SECRET=<GOCSPX-...>
GMAIL_READ_ENABLED=true
```

Después, una sola vez, autorizá el token:

```bash
cd cognitive-os/backend
uv run python scripts/auth_google.py
```

Se abre el navegador, elegí tu cuenta, **“Continuar”** en la pantalla
de “Google no verificó esta app” (botón pequeño abajo a la izquierda
**“Configuración avanzada”** → **“Ir a Cognitive OS (no seguro)”**),
aceptá los permisos. Listo.

---

## A.3 · GODADDY_API_KEY / GODADDY_API_SECRET (developer.godaddy.com)

**Qué habilita:** cambios DNS en GoDaddy vía Action Plane (siempre
dry-run + aprobación humana por defecto).

### Paso 1 — Portal de desarrolladores

1. Andá a **https://developer.godaddy.com**.
2. Arriba a la derecha, botón **“Sign In”** (texto blanco sobre fondo
   verde GoDaddy, o link “Sign In” según el tema). Logueate con tu
   cuenta GoDaddy normal (la misma del dominio).

### Paso 2 — Crear la API Key

1. Una vez logueado, arriba a la derecha hacé click en **tu nombre/
   avatar** → del menú elegí **“API Keys”**. (Atajo directo:
   **https://developer.godaddy.com/keys**.)
2. Botón **“Create New API Key”** (botón verde, a la derecha o centro
   de la página).
3. **Name:** `cognitive-os`.
4. **Environment:** elegí el desplegable. Hay dos opciones:
   - **OTE / Test** — entorno de pruebas, no toca DNS real.
     **Empezá por acá** para probar sin riesgo.
   - **Production** — toca el DNS real de tus dominios.
5. Botón **“Next”** / **“Create”** (verde).
6. Aparece un cuadro con **“Key”** y **“Secret”**. El **Secret se
   muestra una sola vez** — copialo ahora con el ícono de copiar (dos
   cuadraditos) y guardalo. Si lo perdés, hay que regenerar.

**Dónde pegarlo** — en `cognitive-os/.env`:

```
GODADDY_API_KEY=<la Key>
GODADDY_API_SECRET=<el Secret>
GODADDY_ENABLED=true                     # alias correcto (NO ENABLE_GODADDY)
GODADDY_DNS_DRY_RUN_ONLY=true            # dejá true hasta estar 100% seguro
GODADDY_ALLOW_PRODUCTION_WRITES=false    # true solo para escrituras DNS reales
GODADDY_ALLOWED_DOMAINS=tudominio.com    # CSV de dominios permitidos
# Nota: hay dos entornos GoDaddy. Producción autentica contra
# api.godaddy.com (GODADDY_BASE_URL por defecto). Las keys OTE/Test solo
# sirven contra api.ote-godaddy.com.
```

> Empezá con OTE y `GODADDY_DNS_DRY_RUN_ONLY=true`. Para escrituras
> reales en producción hay que poner `GODADDY_DNS_DRY_RUN_ONLY=false` +
> `GODADDY_ALLOW_PRODUCTION_WRITES=true` + aprobación humana. No lo
> hagas hasta haber probado en OTE.

---

## A.4 · HF_TOKEN (Hugging Face)

**Qué habilita:** el reranker de Hugging Face y acceso al Hub para
modelos.

### Pasos

1. Andá a **https://huggingface.co**. Si no tenés cuenta: botón
   **“Sign Up”** (arriba a la derecha, texto oscuro). Si ya tenés:
   **“Log In”**.
2. Una vez dentro, click en **tu avatar circular** (esquina superior
   derecha) → menú desplegable → **“Settings”**.
3. En la barra lateral izquierda de Settings, click en **“Access
   Tokens”**. (Atajo directo:
   **https://huggingface.co/settings/tokens**.)
4. Botón **“+ Create new token”** (botón negro o azul oscuro, arriba a
   la derecha del listado). Click.
5. En el formulario:
   - **Token name:** `cognitive-os`.
   - **Token type / permisos:** elegí **“Read”** (es suficiente; no
     necesita Write). Si ves la vista nueva de “Fine-grained”, dejá
     solo permisos de **lectura de repos públicos/Hub**.
6. Botón **“Create token”** (negro, abajo).
7. Se muestra el token (`hf_...`) **una sola vez**. Botón **“Copy”** al
   lado. Copialo.

**Dónde pegarlo** — en `cognitive-os/.env`:

```
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## A.5 · SUPERMEMORY_API_KEY (Supermemory)

**Qué habilita:** memoria personal cross-sesión del asistente de
desarrollo.

### Pasos

1. Andá a **https://app.supermemory.ai**.
2. Botón **“Sign in”** / **“Get started”** (botón destacado, suele ser
   negro o de color de marca). Registrate o logueate (acepta Google/
   GitHub login).
3. Ya dentro, en el dashboard, buscá en la barra lateral o en el menú
   de tu perfil la sección **“API Keys”** o **“Developer”**. Atajo:
   **https://app.supermemory.ai/dashboard** → pestaña **“API Keys”**.
4. Botón **“Create API Key”** / **“+ New key”**. Click.
5. Dale un nombre (`cognitive-os`) y confirmá. Copiá la key que aparece
   (se muestra una vez).

**Dónde pegarlo** — en `cognitive-os/.env`:

```
SUPERMEMORY_API_KEY=<la key>
```

> Esta es una integración del cockpit de desarrollo (MCP). Si no usás
> Supermemory, podés dejarla pendiente sin problema.

---

## A.6 · GITHUB_PERSONAL_ACCESS_TOKEN (GitHub)

**Qué habilita:** el MCP de GitHub remoto (operaciones sobre repos).

### Pasos

1. Andá a **https://github.com** y logueate.
2. Click en **tu foto de perfil** (esquina superior derecha, círculo) →
   menú → **“Settings”** (al fondo del menú).
3. Barra lateral izquierda, bajá hasta el final: **“Developer
   settings”** (último item, ícono `<>`). Click.
4. Izquierda: **“Personal access tokens”** → elegí **“Fine-grained
   tokens”** (recomendado) o **“Tokens (classic)”**. Atajo fine-grained:
   **https://github.com/settings/tokens?type=beta**.
5. Botón verde **“Generate new token”** (arriba a la derecha).
6. Formulario:
   - **Token name:** `cognitive-os`.
   - **Expiration:** elegí 90 días o lo que prefieras.
   - **Repository access:** **“Only select repositories”** y elegí los
     repos que quieras exponer (o “Public repositories (read-only)” si
     solo es lectura).
   - **Permissions → Repository permissions:** poné **“Contents: Read-
     only”** (suficiente para lectura). No des permisos de escritura si
     no los necesitás.
7. Abajo, botón verde **“Generate token”**.
8. Se muestra el token (`github_pat_...`) **una sola vez**. Ícono de
   copiar al lado. Copialo.

**Dónde pegarlo** — en `cognitive-os/.env`:

```
GITHUB_PERSONAL_ACCESS_TOKEN=github_pat_xxxxxxxxxxxxxxxxxxxx
```

---

# PARTE B — Las demás (ya configuradas en este host)

Documentadas por si necesitás **rotarlas, rehacerlas o entenderlas**.

---

## B.1 · Secretos locales (sin web): JWT, Postgres, Neo4j, Weaviate

No se obtienen de ninguna web — los genera un script local:

```bash
cd cognitive-os
bash scripts/init_env.sh
```

Esto crea/rellena `.env` con valores aleatorios fuertes para
`JWT_SECRET`, `POSTGRES_PASSWORD`, `NEO4J_PASSWORD`, `WEAVIATE_API_KEY`.
Si ya existen, no los pisa. Para **rotar** uno, borrá esa línea del
`.env` y volvé a correr el script (ojo: rotar `POSTGRES_PASSWORD`
requiere recrear el contenedor o actualizar el password en Postgres).

---

## B.2 · PRIMARY_LLM_API_KEY (DeepSeek)

**Qué habilita:** chat, research, document analysis (LLM base).

1. Andá a **https://platform.deepseek.com**.
2. Botón **“Sign in”** / **“Log in”** (arriba a la derecha). Registrate
   con email o Google.
3. Barra lateral izquierda → **“API keys”**.
4. Botón **“Create new API key”** (botón azul). Ponele nombre
   `cognitive-os` → **“Create”**.
5. Copiá la key (`sk-...`) — se muestra una vez.

`.env`: `PRIMARY_LLM_API_KEY=sk-...`

---

## B.3 · EMBEDDINGS_API_KEY (Google AI Studio / Gemini)

**Qué habilita:** RAG, búsqueda semántica, retrieval con Weaviate.

1. Andá a **https://aistudio.google.com/apikey**.
2. Logueate con tu cuenta de Google.
3. Botón azul **“Create API key”** (centro/derecha).
4. Si te pide elegir un proyecto Google Cloud, elegí el `cognitive-os`
   (o “Create API key in new project”).
5. Copiá la key (`AIza...`).

`.env`: `EMBEDDINGS_API_KEY=AIza...`

---

## B.4 · GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET (Calendar + Drive)

**Qué habilita:** Google Calendar y Drive vía Action Plane.

Mismo procedimiento que **A.2** (Google Cloud Console → OAuth Desktop
client), pero en el Paso 2 habilitá **dos APIs** en vez de Gmail:

- Buscá y **HABILITAR** **“Google Calendar API”**.
- Buscá y **HABILITAR** **“Google Drive API”**.

Podés **reutilizar el mismo cliente OAuth Desktop** (no hace falta uno
nuevo). Copiá Client ID y Secret.

`.env`:

```
GOOGLE_CLIENT_ID=<...apps.googleusercontent.com>
GOOGLE_CLIENT_SECRET=GOCSPX-...
ENABLE_GOOGLE_CALENDAR=true
ENABLE_GOOGLE_DRIVE=true
```

Luego una vez: `uv run python scripts/auth_google.py` (igual que A.2).

---

## B.5 · GOOGLE_MAPS_API_KEY (Maps + Routes)

**Qué habilita:** `/maps` (Telegram), rutas con tráfico, geocoding.

1. En **https://console.cloud.google.com**, mismo proyecto.
2. Menú **☰** → **“APIs y servicios”** → **“Biblioteca”**. Habilitá
   (botón azul **“HABILITAR”**) estas dos:
   - **“Routes API”**
   - **“Geocoding API”** (y opcionalmente **“Maps JavaScript API”**).
3. Menú **☰** → **“APIs y servicios”** → **“Credenciales”**.
4. Botón **“+ CREAR CREDENCIALES”** → **“Clave de API”** (“API key”).
5. Se crea y muestra la key (`AIza...`). Botón **“RESTRINGIR CLAVE”**
   (recomendado): en **“Restricciones de API”** elegí **“Restringir
   clave”** y tildá solo **Routes API** y **Geocoding API**. **GUARDAR**.

`.env`:

```
GOOGLE_MAPS_API_KEY=AIza...
ENABLE_MAPS_ROUTING=true
```

---

## B.6 · ELEVENLABS_API_KEY (voz)

**Qué habilita:** `/voice/speak` y `/voice/transcribe`.

1. Andá a **https://elevenlabs.io** → **“Sign up”** / **“Log in”**.
2. Click en **tu avatar** (abajo a la izquierda o arriba a la derecha)
   → **“Profile + API key”** o andá directo a
   **https://elevenlabs.io/app/settings/api-keys**.
3. Botón **“Create API Key”** → nombre `cognitive-os` → **“Create”**.
4. Copiá la key (ícono copiar). Se muestra una vez.

`.env`: `ELEVENLABS_API_KEY=...` (+ `VOICE_ENABLED=true`)

---

## B.7 · MAIL_GODADDY_USERNAME / MAIL_GODADDY_PASSWORD (correo personal)

**Qué habilita:** mail personal IMAP/SMTP de GoDaddy (lectura +
propuesta de respuestas; envío solo con aprobación humana).

- **Username:** es tu dirección de correo completa de GoDaddy
  (`tunombre@tudominio.com`).
- **Password:** la contraseña de ese buzón. **Si tenés 2FA activado**
  en la cuenta de correo, necesitás una **“app password”**:
  1. Entrá a tu webmail GoDaddy (**https://email.godaddy.com** o el
     panel de Microsoft 365 si tu plan es ese).
  2. Ajustes de cuenta → **“Seguridad”** → **“Contraseñas de
     aplicación”** → **“Crear”**. Copiá la generada.
- Los servidores IMAP/SMTP suelen ser `imap.secureserver.net` (993) y
  `smtpout.secureserver.net` (465/587); ya vienen por defecto en la
  config, ajustá en `.env` solo si tu plan difiere.

`.env`:

```
MAIL_GODADDY_USERNAME=tunombre@tudominio.com
MAIL_GODADDY_PASSWORD=<password o app password>
MAIL_ENABLED=true
MAIL_REQUIRE_APPROVAL_FOR_SEND=true     # NO lo cambies
```

---

## B.8 · Búsqueda web: TAVILY / BRAVE / EXA

Las tres son del mismo estilo: registrarse, ir a “API keys”, crear,
copiar.

- **Tavily** — **https://app.tavily.com** → registrate → panel
  **“API Keys”** → **“Create”** → copiá (`tvly-...`).
  `.env`: `TAVILY_API_KEY=tvly-...`
- **Brave Search** — **https://api.search.brave.com/app/keys** →
  logueate → **“Add API key”** / **“Subscribe”** (Brave pide elegir un
  plan; hay uno gratis) → copiá la key.
  `.env`: `BRAVE_SEARCH_API_KEY=...`
- **Exa** — **https://dashboard.exa.ai/api-keys** → logueate → botón
  **“Create API key”** → copiá.
  `.env`: `EXA_API_KEY=...`

---

## B.9 · LANGSMITH_API_KEY (trazas)

**Qué habilita:** trazas runtime de LangGraph en LangSmith.

1. Andá a **https://smith.langchain.com** → **“Sign up”** / **“Log
   in”** (acepta login con Google/GitHub).
2. Abajo a la izquierda, ícono de **engranaje** o tu nombre →
   **“Settings”**. Atajo: **https://smith.langchain.com/settings**.
3. Pestaña **“API Keys”** → botón **“Create API Key”** (botón de
   color de marca, normalmente violeta/azul).
4. Elegí **“Personal Access Token”** o **“Service key”**, nombre
   `cognitive-os`, **“Create”**. Copiá (`lsv2_...`).

`.env`: `LANGSMITH_API_KEY=lsv2_...` (+ `LANGSMITH_TRACING=true` si
querés trazas activas).

---

## B.10 · TELEGRAM_BOT_TOKEN (bot de Telegram)

**Qué habilita:** los 37 slash commands del bot.

### Pasos (dentro de la app de Telegram, no en una web)

1. Abrí Telegram. En el buscador escribí **`@BotFather`** y abrí el
   chat con la cuenta verificada (tilde azul, nombre “BotFather”).
2. Mandá el comando **`/newbot`**.
3. BotFather pregunta el **nombre** del bot (display name): escribí
   `Cognitive OS`.
4. Pregunta el **username**: tiene que terminar en `bot`, p. ej.
   `cognitiveos_tu_alias_bot`. Mandalo.
5. BotFather responde con un mensaje que incluye **“Use this token to
   access the HTTP API:”** seguido del token
   (`1234567890:AAxxxxxxxxxxxxxxxxxxxx`). Ese es el token. Copialo.

### Tu user_id (para la allow-list)

1. En Telegram buscá **`@userinfobot`**, abrí el chat, mandá cualquier
   mensaje (o `/start`). Te responde con tu **Id** (un número, p. ej.
   `123456789`). Ese es tu `user_id`.

`.env`:

```
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=1234567890:AAxxxxxxxxxxxxxxxxxxxx
TELEGRAM_AUTHORIZED_USER_IDS=123456789      # CSV si hay varios
```

Probá: mandale `/start` a tu bot. Si tu id está en la lista, responde
con los comandos.

---

# PARTE C — Verificación final

1. Guardá `.env` (en `cognitive-os/.env`, **nunca** lo subas a git).
2. Reverificá:

   ```bash
   cd cognitive-os
   bash scripts/init_credentials.sh
   ```

   Cada credencial que pegaste bien pasa de `OPT ○` / `REQ ✗` a
   `OK ✓`.
3. Si tocaste Google (Gmail/Calendar/Drive), corré una sola vez:

   ```bash
   cd cognitive-os/backend
   uv run python scripts/auth_google.py
   ```
4. Reiniciá la pila para que tome el `.env` nuevo:

   ```bash
   ~/Escritorio/Reiniciar\ Cognitive\ OS.sh
   ```
5. En el panel, andá a **Health** y a **Sistema** (ConfigurationView):
   cada capacidad que habilitaste debe pasar a `ready`/`configured`.

## Tabla resumen — variable `.env` por credencial

| Credencial | Variable(s) `.env` | Web |
|---|---|---|
| Cifrado payload | `ACTION_PAYLOAD_ENCRYPTION_KEY` | (comando local) |
| Gmail digest | `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_READ_ENABLED` | console.cloud.google.com |
| GoDaddy DNS | `GODADDY_API_KEY`, `GODADDY_API_SECRET`, `GODADDY_ENABLED` | developer.godaddy.com |
| Hugging Face | `HF_TOKEN` | huggingface.co/settings/tokens |
| Supermemory | `SUPERMEMORY_API_KEY` | app.supermemory.ai |
| GitHub MCP | `GITHUB_PERSONAL_ACCESS_TOKEN` | github.com/settings/tokens |
| LLM base | `PRIMARY_LLM_API_KEY` | platform.deepseek.com |
| Embeddings | `EMBEDDINGS_API_KEY` | aistudio.google.com/apikey |
| Calendar+Drive | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | console.cloud.google.com |
| Maps | `GOOGLE_MAPS_API_KEY` | console.cloud.google.com |
| Voz | `ELEVENLABS_API_KEY` | elevenlabs.io/app/settings/api-keys |
| Mail personal | `MAIL_GODADDY_USERNAME`, `MAIL_GODADDY_PASSWORD` | email.godaddy.com |
| Web search | `TAVILY_API_KEY` / `BRAVE_SEARCH_API_KEY` / `EXA_API_KEY` | app.tavily.com / api.search.brave.com / dashboard.exa.ai |
| Trazas | `LANGSMITH_API_KEY` | smith.langchain.com/settings |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_AUTHORIZED_USER_IDS` | @BotFather (app Telegram) |
| Secretos locales | `JWT_SECRET`, `POSTGRES_PASSWORD`, `NEO4J_PASSWORD`, `WEAVIATE_API_KEY` | `bash scripts/init_env.sh` |

> Fuente de verdad de qué credenciales existen y qué habilitan:
> `backend/src/cognitive_os/core/credentials_inventory.py` (lo lee el
> endpoint `/system/credentials-status` y el wizard
> `scripts/init_credentials.sh`). Si algún día el código agrega una
> credencial nueva, aparece sola en el wizard; actualizá esta guía
> entonces.
