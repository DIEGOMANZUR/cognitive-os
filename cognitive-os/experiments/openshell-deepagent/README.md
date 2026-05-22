# OpenShell DeepAgent Experiment

> **Estado actual (2026-05-22):** experimento opcional. Aunque la postura
> global de Cognitive OS en este PC es baja fricción, OpenShell sigue siendo
> un sandbox separado: debe reportar disponibilidad real, registrar eventos y
> fallar explícitamente si vendor/Docker/gateway no están listos.

Integracion opcional de OpenShell DeepAgent para Cognitive OS.

No confundir con **OpenHarness** (HKUDS): la fusión de investigación con QueryEngine
está documentada en `docs/OPENHARNESS_FUSION.md` y vive en `backend/src/cognitive_os/integrations/`.

El vendor oficial se clona en `vendor/openshell-deepagent` y no forma parte del codigo
versionable del backend. OpenShell queda deshabilitado por defecto y solo se usa como
sandbox aislado cuando Cognitive OS lo autoriza.
