import type { ExperimentSnapshotSource } from '@luml/experiments'
import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import type { ArchiveFile } from '@/api/slices/workspace/workspace.interface'

// As the SDK's SNAPSHOT_MEMBERS: generation 2 stores the raw database, generation 1 a zip of it.
const SNAPSHOT_MEMBERS = ['exp.db', 'exp.db.zip']

export function findSnapshotMember(files: ArchiveFile[]): ArchiveFile | undefined {
  return SNAPSHOT_MEMBERS.map((name) => files.find((file) => file.name === name)).find(Boolean)
}

/** A raw database is read by Range requests to its member; a zipped one is fetched whole. */
export async function loadSnapshotSource(
  path: string,
  member: ArchiveFile,
  signal: AbortSignal,
): Promise<ExperimentSnapshotSource> {
  const url = await workspaceApi.fileUrl(path, member.name)
  if (!member.name.endsWith('.zip')) return { kind: 'range', url, offset: 0, size: member.size }
  const response = await fetch(url, { signal })
  if (!response.ok) throw new Error(`Could not read the experiment database (${response.status})`)
  return { kind: 'zip', buffer: await response.arrayBuffer() }
}
