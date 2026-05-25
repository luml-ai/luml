import { api } from '@/lib/api';
import { ref } from 'vue';
export const useArtifactsTags = () => {
    const tags = ref([]);
    async function loadTags(organizationId, orbitId, collectionId) {
        const collectionDetails = await api.orbitCollections.getCollection(organizationId, orbitId, collectionId);
        tags.value = collectionDetails.artifacts_tags;
    }
    function getTagsByQuery(query) {
        return [query, ...tags.value.filter((tag) => tag.toLowerCase().includes(query.toLowerCase()))];
    }
    return { loadTags, getTagsByQuery };
};
