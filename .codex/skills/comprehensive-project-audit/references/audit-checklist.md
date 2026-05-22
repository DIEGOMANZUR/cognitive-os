# Audit Checklist

## Repository
- Root detected
- Git status inspected
- File tree summarized
- Large/generated/vendor dirs excluded from deep manual review unless relevant
- Main source dirs identified
- Entrypoints identified

## Stack
- Languages detected
- Frameworks detected
- Package managers detected
- Lockfiles detected
- Runtime versions detected
- Build/test/lint/typecheck commands detected

## Security
- Secrets scanned
- Auth inspected
- Authorization inspected
- Input validation inspected
- File upload inspected if present
- Dependency audit attempted
- Docker security inspected if present
- CORS/CSRF/session/JWT inspected if present

## Backend
- API routes mapped
- Middleware mapped
- Error handling inspected
- DB access inspected
- Transactions inspected
- Migrations inspected
- Background jobs inspected if present

## Frontend
- Routes mapped
- Auth guards inspected
- State management inspected
- Loading/error/empty states inspected
- Accessibility reviewed
- Forms reviewed

## Tests
- Test framework detected
- Tests executed if safe
- Critical path coverage reviewed
- Mocks reviewed
- CI parity reviewed

## DevOps
- Docker inspected
- Compose inspected
- CI/CD inspected
- Env vars inspected
- Healthchecks inspected
- Logging/observability inspected
- Deployment docs inspected

## Documentation
- README checked against actual commands
- Setup docs checked
- Env docs checked
- Architecture docs checked
- API docs checked if present
