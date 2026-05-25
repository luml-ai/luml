export declare const useArtifactsTags: () => {
    loadTags: (organizationId: string, orbitId: string, collectionId: string) => Promise<void>;
    getTagsByQuery: (query: string) => any[];
};
