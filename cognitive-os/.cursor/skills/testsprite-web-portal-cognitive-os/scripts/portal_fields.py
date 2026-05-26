#!/usr/bin/env python3
"""Print safe TestSprite Web Portal field values for Cognitive OS."""

from __future__ import annotations

import argparse
import textwrap


API_INSTRUCTIONS = """\
Cognitive OS API Contract Full. Use https://cognitive-api.doctormanzur.com as the backend base. Public endpoints are GET /health, GET /openapi.json, GET /docs, GET /redoc. All other endpoints require Authorization: Bearer <JWT>. Expected auth guards: missing token 401, invalid token 401, expired token 401 JWT has expired, insufficient role 403 forbidden_role. Do not mark expected guards as bugs. Do not execute real-world destructive actions: no mail send, no mail draft, no approve-send, no DNS write, no destructive sandbox execution, no dangerous tool execution, no safety flag mutation, no JWT secret rotation, no admin user mutation. Guard tests are allowed only when expected result is controlled 400/403/409/feature_disabled/dry_run_only/forbidden with no side effect. Mail is read-only in normal flow. Treat provider disabled/degraded as acceptable only if response is explicit and non-5xx.
"""

UI_INSTRUCTIONS = """\
Cognitive OS UI SPA Full. Use only https://cognitive.doctormanzur.com/ as the entry URL, preferably with #cogos_token=<JWT_WITHOUT_BEARER> when available. This is a single-page app: do NOT directly navigate to /dashboard, /health, /mail, /chat, /documents, /settings, /jobs, /approvals, /research, or /code-director because direct server paths are expected 404. Do NOT click "Usar JWT local automatico" and do NOT call POST /auth/local-token from the external TestSprite portal; Cloudflare may block external agent signatures. If a Test Account password is provided, treat it as a JWT, not as a login password: set localStorage.cogos.token to that credential value, set localStorage.cogos.api to https://cognitive-api.doctormanzur.com, set localStorage.cogos.token.source to manual, then reload /. If direct localStorage scripting is unavailable, open Conexion, paste the Test Account password into "JWT sin prefijo Bearer", confirm API base is https://cognitive-api.doctormanzur.com, click Guardar, then return to Dashboard. Navigate views only through sidebar, hotkeys 1-9, and Ctrl+K command palette. Cover Dashboard, Chat, DeepAgents, Skills, Memoria, Asistente, Mail read-only, Documentos, Document Analysis, Jobs, Aprobaciones, Google Ops, Research, Code Director, Sandbox, LangSmith, Audit log, Health, Sistema, Conexion, Notifications, Command Palette, and responsive behavior. Do not accept demo, fixture, or provisional UI fallbacks as success. Assert connected or controlled degraded state after seed. Fail on critical console errors, hydration/chunk errors, CORS, mixed content, infinite loading, false green health, dead critical buttons, or real network requests to localhost/127.0.0.1. Mail must remain read-only: do not create drafts, sync mail, approve send, or send email. Do not execute destructive actions.
"""


def print_ui() -> None:
    print("Test type: Frontend (URLs)")
    print(
        "Website URL: "
        "https://cognitive.doctormanzur.com/#cogos_token=<JWT_WITHOUT_BEARER>"
    )
    print("Test Account username/email: local-operator-jwt")
    print(
        "Test Account password: <contents of /home/jgonz/Escritorio/testsprite/"
        "cognitive_os_testsprite_stable_jwt.txt, without Bearer prefix>"
    )
    print("\nExtra context/instructions:\n")
    print(textwrap.dedent(UI_INSTRUCTIONS).strip())


def print_api() -> None:
    print("Test type: Backend (APIs)")
    print("Backend base URL: https://cognitive-api.doctormanzur.com")
    print("OpenAPI URL: https://cognitive-api.doctormanzur.com/openapi.json")
    print("Authentication Type: Bearer for protected endpoints")
    print("Credential / Key: <fresh Cognitive OS JWT, without Bearer prefix>")
    print("JWT source: see CREDENTIALS.md or mint via POST /auth/local-token")
    print("Never paste TESTSPRITE_API_KEY here.")
    print("\nExtra testing instructions:\n")
    print(textwrap.dedent(API_INSTRUCTIONS).strip())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", choices=("ui", "api"))
    args = parser.parse_args()

    if args.suite == "ui":
        print_ui()
    else:
        print_api()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
