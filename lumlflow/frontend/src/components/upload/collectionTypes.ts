import { UploadTypeEnum } from './upload.interface'

/** What an upload will actually put in the collection. */
export type ArtifactKind = 'model' | 'experiment'

/**
 * The kinds one upload produces. This mirrors the daemon's `upload_artifact`:
 * `experiment` sends the `.luml` export, `model` sends every tracker model,
 * and `auto` sends the one model with the experiment embedded when there is
 * exactly one, and otherwise the models plus the experiment.
 */
export function requiredArtifactKinds(type: UploadTypeEnum, modelCount: number): ArtifactKind[] {
  switch (type) {
    case UploadTypeEnum.EXPERIMENT:
      return ['experiment']
    case UploadTypeEnum.MODEL:
      return ['model']
    default:
      if (modelCount === 1) return ['model']
      if (modelCount === 0) return ['experiment']
      return ['model', 'experiment']
  }
}

/**
 * LUML's own rule, applied before the request rather than read back as a 400:
 * a `mixed` collection takes anything, and any other type names the kinds it
 * takes (`model_experiment` takes models and experiments).
 */
export function collectionAccepts(collectionType: string, kinds: ArtifactKind[]): boolean {
  if (collectionType === 'mixed') return true
  return kinds.every((kind) => collectionType.split('_').includes(kind))
}
