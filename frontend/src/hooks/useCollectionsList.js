import { api } from '@/lib/api';
import { computed, ref, watch } from 'vue';
import { useCollectionsStore } from '@/stores/collections';
export const useCollectionsList = (limit = 20, syncStore = true, types) => {
    const collectionsStore = useCollectionsStore();
    const savedCursors = ref([]);
    const requestInfo = ref(null);
    const isLoading = ref(false);
    const searchQuery = ref('');
    const typesQuery = ref(types ?? []);
    const collectionsList = ref([]);
    const pageIndex = computed(() => {
        return savedCursors.value.length;
    });
    function setRequestInfo(info) {
        requestInfo.value = info;
    }
    async function getInitialPage() {
        isLoading.value = true;
        const cursor = null;
        const response = await getCollectionsData(cursor);
        addCollectionsToList(response.items);
        savedCursors.value.push(response.cursor);
        isLoading.value = false;
    }
    async function getNextPage() {
        const cursor = getNextPageCursor();
        if (!cursor)
            return;
        isLoading.value = true;
        const response = await getCollectionsData(cursor);
        addCollectionsToList(response.items);
        savedCursors.value.push(response.cursor);
        isLoading.value = false;
    }
    async function getCollectionsData(cursor) {
        if (!requestInfo.value)
            throw new Error('Request info not set');
        return await api.orbitCollections.getCollectionsList(requestInfo.value.organizationId, requestInfo.value.orbitId, { cursor, limit, search: searchQuery.value, types: typesQuery.value });
    }
    function getNextPageCursor() {
        return savedCursors.value[savedCursors.value.length - 1] ?? null;
    }
    function reset() {
        setCollectionsList([]);
        savedCursors.value = [];
        requestInfo.value = null;
    }
    function addCollectionsToList(collections) {
        const existingCollectionsIds = collectionsList.value.map((collection) => collection.id);
        const newCollections = collections.filter((collection) => !existingCollectionsIds.includes(collection.id));
        setCollectionsList([...collectionsList.value, ...newCollections]);
    }
    function setCollectionsList(collections) {
        if (syncStore) {
            collectionsStore.setCollectionsList(collections);
        }
        else {
            collectionsList.value = collections;
        }
    }
    function setSearchQuery(query) {
        searchQuery.value = query;
    }
    async function onLazyLoad(event) {
        if (isLoading.value)
            return;
        const { last } = event;
        if (last === pageIndex.value * limit) {
            await getNextPage();
        }
    }
    function setTypesQuery(types) {
        typesQuery.value = types;
    }
    if (syncStore) {
        watch(() => collectionsStore.collectionsList, (storeCollectionsList) => {
            collectionsList.value = storeCollectionsList;
        }, { immediate: true });
    }
    return {
        setRequestInfo,
        getInitialPage,
        collectionsList,
        getNextPage,
        isLoading,
        pageIndex,
        reset,
        addCollectionsToList,
        searchQuery,
        setSearchQuery,
        onLazyLoad,
        typesQuery,
        setTypesQuery,
    };
};
