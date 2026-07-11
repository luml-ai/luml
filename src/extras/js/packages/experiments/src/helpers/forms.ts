import { ZodError } from 'zod'

export function mapZodErrors<T>(error: ZodError<T>): Record<string, string> {
  const formatted: Record<string, string> = {}

  error.issues.forEach((issue: any) => {
    const path = issue.path.join('.')
    formatted[path] = issue.message
  })

  return formatted
}
