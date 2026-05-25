import type { GetArtifactsListParams, Artifact, ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces';
import type { VirtualScrollerLazyEvent } from 'primevue';
interface RequestInfo {
    organizationId: string;
    orbitId: string;
    collectionId: string;
}
export declare const useArtifactsList: (limit?: number, syncStore?: boolean, types?: ArtifactTypeEnum[]) => {
    setRequestInfo: (info: RequestInfo) => void;
    getInitialPage: () => Promise<void>;
    list: any;
    getNextPage: () => Promise<void>;
    isLoading: any;
    pageIndex: any;
    reset: () => void;
    addItemsToList: (artifacts: Artifact[]) => void;
    setSortData: (data: Pick<GetArtifactsListParams, "sort_by" | "order">) => void;
    onLazyLoad: (event: VirtualScrollerLazyEvent) => Promise<void>;
    setLoading: (value: boolean) => void;
    setTypesQuery: (types: ArtifactTypeEnum[]) => void;
    typesQuery: any;
};
export {};
