// ESLint flat config for killkrill project
import js from "@eslint/js";

export default [
  js.configs.recommended,
  {
    ignores: [
      "**/node_modules/**",
      "**/dist/**",
      "**/build/**",
      "**/.venv/**",
      "**/__pycache__/**",
      "**/venv/**",
      "**/.pytest_cache/**",
      "**/coverage/**",
      "**/.git/**",
      "**/migrations/**",
      "**/*.min.js",
      "**/vendor/**",
      "**/lib/**",
      // Ignore third-party libraries
      "**/static/js/prism.js",
      "**/static/js/lib/**",
      // Ignore app skeleton templates (not production code)
      "app-skeleton/**",
      // Ignore TypeScript files (separate parser needed)
      "**/*.ts",
      "**/*.tsx",
      // Ignore coverage reports
      "htmlcov/**",
    ],
  },
  {
    files: ["**/*.js", "**/*.mjs", "**/*.cjs"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: {
        // Node.js globals
        console: "readonly",
        process: "readonly",
        Buffer: "readonly",
        __dirname: "readonly",
        __filename: "readonly",
        exports: "writable",
        module: "writable",
        require: "readonly",
        global: "readonly",
        // Browser globals
        window: "readonly",
        document: "readonly",
        navigator: "readonly",
        location: "readonly",
        localStorage: "readonly",
        sessionStorage: "readonly",
        fetch: "readonly",
        FormData: "readonly",
        FileReader: "readonly",
        Event: "readonly",
        Worker: "readonly",
        btoa: "readonly",
        atob: "readonly",
        self: "readonly",
        WorkerGlobalScope: "readonly",
        HTMLElement: "readonly",
        HTMLDataElement: "readonly",
        // Common globals
        setTimeout: "readonly",
        setInterval: "readonly",
        clearTimeout: "readonly",
        clearInterval: "readonly",
        // Library globals (for specific files that use them)
        Vue: "readonly",
        Q: "readonly",
        translations: "readonly",
      },
    },
    rules: {
      // Possible errors
      "no-console": "off", // Allow console in Node.js projects
      "no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
      "no-undef": "error",
      "no-empty": "warn", // Downgrade to warning

      // Best practices
      eqeqeq: "off", // Disable for now (too many violations in existing code)
      "no-eval": "warn", // Downgrade to warning
      "no-implied-eval": "error",
      "no-prototype-builtins": "off", // Disable for now
      "no-useless-escape": "off", // Disable for now
      "no-control-regex": "off", // Disable for now
      "no-cond-assign": "off", // Disable for now

      // Style (minimal - let Prettier handle formatting)
      semi: ["error", "always"],
      quotes: "off", // Disable quotes rule (too strict)
    },
  },
];
