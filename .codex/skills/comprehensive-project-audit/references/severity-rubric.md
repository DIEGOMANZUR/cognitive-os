# Severity Rubric

## CRITICAL
Issue can cause data loss, security breach, total app failure, privilege escalation, broken production deployment, or serious legal/compliance exposure.

## HIGH
Issue can break critical user flows, cause incorrect business logic, expose sensitive data under realistic conditions, or block reliable deployment.

## MEDIUM
Issue creates maintainability risk, partial feature failure, weak test coverage in important areas, poor error handling, or fragile architecture.

## LOW
Issue is minor, localized, cosmetic, or unlikely to cause production impact soon.

## INFO
Observation, improvement, missing documentation, or optional hardening.

Rules:
- Do not inflate severity.
- Confirmed exploit beats theoretical risk.
- Runtime failure beats style preference.
- Missing verification must be marked as unknown, not as a confirmed defect.
