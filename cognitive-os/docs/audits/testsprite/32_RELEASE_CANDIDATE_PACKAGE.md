# Release Candidate Package

## Recommended Profile

```bash
OPERATOR_PROFILE=dedicated_local
LOCAL_AUTONOMY_MODE=full
CODE_DIRECTOR_BUDGET_MODE=soft
```

## Daily Start

```bash
/home/jgonz/Escritorio/cognitive-os.sh start
/home/jgonz/Escritorio/cognitive-os.sh status
```

## Verification

```bash
curl http://127.0.0.1:8000/health
cd cognitive-os && bash scripts/full-qa.sh
cd cognitive-os && bash scripts/stress-qa.sh 3
cd cognitive-os/frontend && npx playwright test
```

## Operations

- Frontend: `http://localhost:3001`.
- API docs: `http://127.0.0.1:8000/docs`.
- Health: use the Health view plus `POST /health/verify`.
- Logs: `/home/jgonz/.cognitive-os/logs`.
- Telegram: launcher starts it when configured.
- Kimi/WebBridge: launcher starts Edge DevTools and WebBridge.
- Action Plane: use preview/request/approval flow; no direct unsafe dispatch.
- Mail: read/digest/propose text only. Do not send or draft in normal flow.

## Do Not Do

- Do not send mail or create drafts from normal QA.
- Do not apply DNS writes.
- Do not use production DB data for destructive tests.
- Do not store JWTs or API keys in reports.
- Do not turn dedicated_local/full into strict behavior.

## Residual Risk

No release-blocking product or TestSprite defect remains known. The previous TestSprite frontend/E2E HTTP 500 was closed by split TestSprite runs and equivalent replacement cases for the two runner-broken IDs.
