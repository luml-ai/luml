import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces';
export declare const useArtifactUpload: () => {
    progress: any;
    upload: (file: File, name: string, type: ArtifactTypeEnum, description: string, tags: string[], requestInfo?: {
        organizationId: string;
        orbitId: string;
        collectionId: string;
    }) => Promise<any>;
};
