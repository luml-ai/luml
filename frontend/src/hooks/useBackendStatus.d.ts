export declare function useBackendStatus(): {
    isOffline: any;
    isLoading: any;
    versionMismatch: any;
    check: () => Promise<boolean>;
};
