/// <reference types="vite/client" />

// Optional on purpose: neither is set for a plain `npm run build`, and code
// that reads them has to say what it does without one.
interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  readonly VITE_LUML_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
