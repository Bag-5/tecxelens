// Flat ESLint config.
//
// The previous version was `import nextConfig from "eslint-config-next"`.
// That resolves to eslint-config-next's *legacy* (eslintrc) entry point, which
// begins by loading @rushstack/eslint-patch to monkey-patch ESLint's internal
// module resolution. That patch targets ESLint 8 internals, so under ESLint 9 it
// throws "Failed to patch ESLint because the calling module was not
// recognized" while loading the config -- before a single file is linted. There
// is no flag that fixes it; `eslint-config-next/flat` does not exist in 15.5.20,
// and `next/core-web-vitals` cannot be used as a fallback because it extends
// that same crashing index.js.
//
// So the config is composed from the underlying plugins directly. They are flat-
// config capable on their own, which sidesteps the patch entirely, and the rule
// set below mirrors what the legacy config enabled so nothing is silently lost.
import js from "@eslint/js";
import globals from "globals";
import nextPlugin from "@next/eslint-plugin-next";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import tsPlugin from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";

export default [
  {
    ignores: [".next/**", "node_modules/**", "out/**", "next-env.d.ts"],
  },

  js.configs.recommended,
  react.configs.flat.recommended,
  react.configs.flat["jsx-runtime"],
  // `recommended` in eslint-plugin-react-hooks 5.x still declares plugins as an
  // array of strings, which flat config rejects outright. `recommended-latest`
  // is the same rule set with a plugin object, so it is the flat-safe one.
  reactHooks.configs["recommended-latest"],
  // Unlike the others this one is an array of config objects, not a single one.
  ...tsPlugin.configs["flat/recommended"],

  {
    files: ["**/*.{js,jsx,mjs,ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      globals: { ...globals.browser, ...globals.node },
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        ecmaFeatures: { jsx: true },
      },
    },
    settings: {
      react: { version: "detect" },
    },
    plugins: {
      // @next/eslint-plugin-next 15.5.20 predates flat config, so its shareable
      // configs are eslintrc-shaped ({ plugins: ["@next/next"], extends: [] })
      // and flat config rejects them. Register the plugin here and take only its
      // rules, which is the documented way to use a pre-flat shareable config.
      "@next/next": nextPlugin,
    },
    rules: {
      ...nextPlugin.configs.recommended.rules,
      // next/core-web-vitals is legacy-shaped ({ plugins: [], extends: [] }),
      // so only its rules can be lifted into flat config. Applied after
      // next/recommended, which it would otherwise extend.
      ...nextPlugin.configs["core-web-vitals"].rules,

      // Matches the legacy config's intent: the App Router supplies the JSX
      // runtime, and this codebase is fully typed so prop-types adds nothing.
      "react/react-in-jsx-scope": "off",
      "react/prop-types": "off",

      // Underscore-prefixed args/vars are the conventional "intentionally
      // unused" marker, and this codebase uses it (e.g. catch { /* fallback */ }).
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },
];