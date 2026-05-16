#!/usr/bin/env bash
# Parche idempotente para mcp-weaviate 0.2.0:
#   1) config.py: NO borrar api_key cuando connection_type == "local".
#   2) weaviate_client.py: pasar Auth.api_key(...) a connect_to_local.
#
# El paquete vive en el cache de uv; si uv recrea el archive, este script
# vuelve a aplicar los patches. Idempotente: si ya están aplicados, no hace
# nada y no falla.
set -euo pipefail

# Localizar el dir del archive de uvx donde vive mcp-weaviate.
ARCHIVE_BASE="${HOME}/.cache/uv/archive-v0"
PKG_DIR=""
for d in "${ARCHIVE_BASE}"/*/lib/python*/site-packages/src; do
  if [[ -f "${d}/main.py" && -f "${d}/weaviate_client.py" ]]; then
    if grep -q "Weaviate MCP" "${d}/main.py" 2>/dev/null; then
      PKG_DIR="${d}"
      break
    fi
  fi
done

if [[ -z "${PKG_DIR}" ]]; then
  echo "patch-mcp-weaviate: paquete no encontrado en ${ARCHIVE_BASE}" >&2
  echo "Ejecuta primero: uvx mcp-weaviate --help" >&2
  exit 0  # No fallar: opencode aún puede arrancar otros MCPs.
fi

CONFIG="${PKG_DIR}/config.py"
CLIENT="${PKG_DIR}/weaviate_client.py"

# Patch 1: config.py
if ! grep -q "api_key kept for local auth" "${CONFIG}"; then
  python3 - "$CONFIG" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
old = "            # Clear cloud-specific parameters\n            self.cluster_url = None\n            self.api_key = None"
new = "            # Clear cloud-specific parameters (api_key kept for local auth)\n            self.cluster_url = None"
if old in s:
    open(p, "w").write(s.replace(old, new))
    print(f"patched: {p}")
else:
    print(f"skip (pattern not found): {p}")
PY
else
  echo "patch 1 already applied: ${CONFIG}"
fi

# Patch 2: weaviate_client.py
if ! grep -q "auth_credentials=auth" "${CLIENT}"; then
  python3 - "$CLIENT" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
old = """        return weaviate.connect_to_local(
            host=host,
            port=port,
            grpc_port=grpc_port,
            headers=self.config.additional_headers,
        )"""
new = """        from weaviate.classes.init import Auth
        auth = Auth.api_key(self.config.api_key) if self.config.api_key else None
        return weaviate.connect_to_local(
            host=host,
            port=port,
            grpc_port=grpc_port,
            headers=self.config.additional_headers,
            auth_credentials=auth,
        )"""
if old in s:
    open(p, "w").write(s.replace(old, new))
    print(f"patched: {p}")
else:
    print(f"skip (pattern not found): {p}")
PY
else
  echo "patch 2 already applied: ${CLIENT}"
fi
