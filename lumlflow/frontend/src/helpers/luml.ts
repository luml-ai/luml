const DEFAULT_LUML_APP_URL = 'https://app.luml.ai'

export const LUML_APP_URL = (import.meta.env.VITE_LUML_URL || DEFAULT_LUML_APP_URL).replace(
  /\/+$/,
  '',
)

export const LUML_API_KEY_URL = `${LUML_APP_URL}/api-key`
