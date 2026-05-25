import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { api } from '@/lib/api';
import { useRoute } from 'vue-router';
export const useCollectionsStore = defineStore('collections', () => {
    const route = useRoute();
    const collectionsList = ref([]);
    const currentCollection = ref(null);
    const creatorVisible = ref(false);
    const requestInfo = computed(() => {
        if (typeof route.params.organizationId !== 'string')
            throw new Error('Current organization not found');
        if (typeof route.params.id !== 'string')
            throw new Error('Orbit was not found');
        return {
            organizationId: route.params.organizationId,
            orbitId: route.params.id,
        };
    });
    async function createCollection(payload, requestData) {
        const info = requestData ? requestData : requestInfo.value;
        const collection = await api.orbitCollections.createCollection(info.organizationId, info.orbitId, payload);
        setCollectionsList([...collectionsList.value, collection]);
    }
    async function updateCollection(collectionId, payload) {
        const updatedCollection = await api.orbitCollections.updateCollection(requestInfo.value.organizationId, requestInfo.value.orbitId, collectionId, payload);
        const newCollections = collectionsList.value.map((collection) => {
            return collection.id === collectionId ? updatedCollection : collection;
        });
        setCollectionsList(newCollections);
    }
    async function deleteCollection(collectionId) {
        await api.orbitCollections.deleteCollection(requestInfo.value.organizationId, requestInfo.value.orbitId, collectionId);
        const newCollections = collectionsList.value.filter((collection) => collection.id !== collectionId);
        setCollectionsList(newCollections);
    }
    function setCollectionsList(collections) {
        collectionsList.value = collections;
    }
    async function setCurrentCollection(collectionId) {
        const collection = await getCollection(collectionId);
        currentCollection.value = collection;
    }
    function resetCurrentCollection() {
        currentCollection.value = null;
    }
    function reset() {
        collectionsList.value = [];
        resetCurrentCollection();
    }
    function showCreator() {
        creatorVisible.value = true;
    }
    function hideCreator() {
        creatorVisible.value = false;
    }
    async function getCollection(collectionId) {
        return await api.orbitCollections.getCollection(requestInfo.value.organizationId, requestInfo.value.orbitId, collectionId);
    }
    return {
        collectionsList,
        setCollectionsList,
        currentCollection,
        creatorVisible,
        requestInfo,
        createCollection,
        updateCollection,
        deleteCollection,
        reset,
        setCurrentCollection,
        resetCurrentCollection,
        showCreator,
        hideCreator,
        getCollection,
    };
});
