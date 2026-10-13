const FORBIDDEN_CHARS = /[\x00-\x1f\x7f ~^:?*[\\]/

export const LANE_NAME_INVALID_MESSAGE = 'Name must be a valid git branch name'

export function isValidGitBranchName(name: string): boolean {
  if (!name) return false
  if (name === '@') return false
  if (name.startsWith('/') || name.endsWith('/')) return false
  if (name.endsWith('.')) return false
  if (name.includes('..')) return false
  if (name.includes('@{')) return false
  if (name.includes('//')) return false
  if (FORBIDDEN_CHARS.test(name)) return false

  return name
    .split('/')
    .every((segment) => segment.length > 0 && !segment.startsWith('.') && !segment.endsWith('.lock'))
}
