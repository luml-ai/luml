import type { ITrackArtifact } from '@/lib/api/orbit-tracks/interfaces';
import type { VirtualScrollerLazyEvent } from 'primevue';
interface RequestInfo {
    organizationId: string;
    orbitId: string;
    trackId: string;
}
export declare const useTrackEntriesList: (pageSize?: number) => {
    setRequestInfo: (info: RequestInfo) => void;
    getInitialPage: () => Promise<void>;
    entriesList: any;
    getNextPage: () => Promise<void>;
    isLoading: any;
    pageIndex: any;
    reset: () => void;
    addItemsToList: (entries: ITrackArtifact[]) => void;
    onLazyLoad: (event: VirtualScrollerLazyEvent) => Promise<void>;
};
export {};
