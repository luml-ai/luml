/**
 * The upload dialog offers only the collections LUML would take the upload
 * into. Before this, every collection of the orbit was listed, and picking one
 * of the wrong type came back as "Artifact type is not allowed for this
 * collection type" after the form was filled in.
 */

import { describe, expect, it } from 'vitest'
import { collectionAccepts, requiredArtifactKinds } from '@/components/upload/collectionTypes'
import { UploadTypeEnum } from '@/components/upload/upload.interface'

describe('what an upload sends', () => {
  it('follows the daemon: auto is the one model, else models plus the experiment', () => {
    expect(requiredArtifactKinds(UploadTypeEnum.AUTO, 0)).toEqual(['experiment'])
    expect(requiredArtifactKinds(UploadTypeEnum.AUTO, 1)).toEqual(['model'])
    expect(requiredArtifactKinds(UploadTypeEnum.AUTO, 2)).toEqual(['model', 'experiment'])
    expect(requiredArtifactKinds(UploadTypeEnum.MODEL, 0)).toEqual(['model'])
    expect(requiredArtifactKinds(UploadTypeEnum.EXPERIMENT, 3)).toEqual(['experiment'])
  })
})

describe('which collections take it', () => {
  it('reads the kinds off the collection type, and mixed takes anything', () => {
    expect(collectionAccepts('experiment', ['experiment'])).toBe(true)
    expect(collectionAccepts('model_experiment', ['experiment'])).toBe(true)
    expect(collectionAccepts('model_experiment', ['model', 'experiment'])).toBe(true)
    expect(collectionAccepts('dataset_experiment', ['model'])).toBe(false)
    expect(collectionAccepts('model', ['model', 'experiment'])).toBe(false)
    expect(collectionAccepts('mixed', ['model', 'experiment'])).toBe(true)
  })
})
