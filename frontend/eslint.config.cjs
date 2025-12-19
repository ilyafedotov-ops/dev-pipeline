const coreWebVitals = require("eslint-config-next/core-web-vitals");
const typescript = require("eslint-config-next/typescript");

module.exports = [
  ...coreWebVitals,
  ...typescript,
  {
    ignores: ["eslint.config.cjs"],
  },
  {
    rules: {
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    },
  },
  {
    files: ["components/ui/data-table.tsx"],
    rules: {
      "react-hooks/incompatible-library": "off",
    },
  },
];
