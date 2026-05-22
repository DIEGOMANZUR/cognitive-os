# Codex Supervision Template

Codex must review Claude Code's changes as a strict supervisor.

## Inputs

- Original audit report
- Claude remediation prompt
- Git diff
- Claude final response
- Command outputs
- Relevant files

## Review checks

1. Did Claude fix the requested findings?
2. Did Claude modify unrelated code?
3. Did Claude introduce regressions?
4. Did Claude remove or weaken tests?
5. Did Claude add new dependencies unnecessarily?
6. Did Claude hide errors instead of fixing them?
7. Did Claude preserve public behavior?
8. Did verification commands pass?
9. Did any security posture worsen?
10. Are remaining risks clearly documented?

## Verdicts

Use one:

- APPROVED
- APPROVED WITH WARNINGS
- REJECTED
- BLOCKED
- NEEDS MORE EVIDENCE

If rejected, produce a follow-up prompt addressed directly to Claude Code.
