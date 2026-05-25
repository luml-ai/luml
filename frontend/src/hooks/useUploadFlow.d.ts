import type { UploadReadyEvent } from '@/lib/api/prisma/prisma.interfaces';
export interface UploadEntry {
    uploadId: string;
    runId: string;
    nodeId: string;
    status: 'pending' | 'uploading' | 'completed' | 'failed';
    error: string | null;
    artifact?: ArtifactContext;
}
export interface ArtifactContext {
    artifactId: string;
    organizationId: string;
    orbitId: string;
    collectionId: string;
}
export declare function useUploadFlow(): {
    uploads: any;
    activeUploads: any;
    failedUploads: any;
    worktreesPendingMessage: any;
    getNodeArtifact: (nodeId: string) => ArtifactContext | undefined;
    handleEvent: (eventType: string, data: Record<string, any>) => void;
    handleUploadReady: (data: UploadReadyEvent) => void;
    handleUploadCompleted: (data: {
        upload_id: string;
        run_id: string;
        node_id: string;
    }) => Promise<void>;
    handleUploadFailed: (data: {
        upload_id: string;
        run_id: string;
        node_id: string;
        error: string;
        status: string;
    }) => void;
    handleWorktreesPendingUpload: (data: {
        run_id: string;
        message?: string;
    }) => void;
    retryUpload: (uploadId: string, event: UploadReadyEvent) => Promise<void>;
    resumePendingUploads: (runId: string, collectionId: string, organizationId: string, orbitId: string) => Promise<void>;
};
