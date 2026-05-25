import type { OrbitCollection, OrbitCollectionTypeEnum } from '@/lib/api/orbit-collections/interfaces';
import type { VirtualScrollerLazyEvent } from 'primevue';
interface RequestInfo {
    organizationId: string;
    orbitId: string;
}
export declare const useCollectionsList: (limit?: number, syncStore?: boolean, types?: OrbitCollectionTypeEnum[]) => {
    setRequestInfo: (info: RequestInfo) => void;
    getInitialPage: () => Promise<void>;
    collectionsList: any;
    getNextPage: () => Promise<void>;
    isLoading: any;
    pageIndex: any;
    reset: () => void;
    addCollectionsToList: (collections: OrbitCollection[]) => void;
    searchQuery: any;
    setSearchQuery: (query: string) => void;
    onLazyLoad: (event: VirtualScrollerLazyEvent) => Promise<void>;
    typesQuery: any;
    setTypesQuery: (types: OrbitCollectionTypeEnum[]) => void;
};
export {};
