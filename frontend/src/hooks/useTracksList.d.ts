interface RequestInfo {
    organizationId: string;
    orbitId: string;
}
export declare const useTracksList: (syncStore?: boolean) => {
    setRequestInfo: (info: RequestInfo) => void;
    load: () => Promise<void>;
    tracksList: any;
    isLoading: any;
    reset: () => void;
};
export {};
