import type { ModelArtifact } from '@/lib/api/artifacts/interfaces';
export declare const useExperimentSnapshotsDatabaseProvider: () => {
    init: (models: ModelArtifact[]) => Promise<void>;
};
