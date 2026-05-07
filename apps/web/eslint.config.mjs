import js from "@eslint/js";

export default [
  js.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      parserOptions: { ecmaVersion: "latest", sourceType: "module" },
      globals: {
        React: "readonly",
        File: "readonly",
        FormData: "readonly",
        fetch: "readonly",
        process: "readonly",
      },
    },
    rules: {
      "no-unused-vars": "off",
    },
  },
  { ignores: [".next/**", "node_modules/**"] },
];
