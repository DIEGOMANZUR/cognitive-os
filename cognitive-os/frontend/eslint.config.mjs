import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

/** @type {import("eslint").Linter.Config[]} */
const nextConfigs = require("eslint-config-next/core-web-vitals");

/** @type {import("eslint").Linter.Config[]} */
const eslintConfig = [
  {
    ignores: [".next/**", "node_modules/**", "next-env.d.ts"]
  },
  ...nextConfigs,
  {
    rules: {
      // Reglas experimentales demasiado estrictas para efectos de datos/async habituales en la UI.
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/refs": "off"
    }
  }
];

export default eslintConfig;
