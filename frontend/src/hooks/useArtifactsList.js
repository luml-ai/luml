import { api } from '@/lib/api';
import { computed, ref, watch } from 'vue';
import { useArtifactsStore } from '@/stores/artifacts';
import { useDebounceFn } from '@vueuse/core';
export const useArtifactsList = (limit = 20, syncStore = true, types) => {
    const artifactsStore = useArtifactsStore();
    const abortController = ref(null);
    const savedCursors = ref([]);
    const requestInfo = ref(null);
    const isLoading = ref(false);
    const sortData = ref({
        sort_by: undefined,
        order: undefined,
    });
    const typesQuery = ref(types ?? []);
    const list = ref([]);
    const pageIndex = computed(() => {
        return savedCursors.value.length;
    });
    function setRequestInfo(info) {
        requestInfo.value = info;
    }
    async function getInitialPage() {
        isLoading.value = true;
        const cursor = null;
        const response = await getData(cursor);
        addItemsToList(response.items);
        savedCursors.value.push(response.cursor);
        isLoading.value = false;
    }
    async function getNextPage() {
        const cursor = getNextPageCursor();
        if (!cursor)
            return;
        isLoading.value = true;
        const response = await getData(cursor);
        addItemsToList(response.items);
        savedCursors.value.push(response.cursor);
        isLoading.value = false;
    }
    async function getData(cursor) {
        if (!requestInfo.value)
            throw new Error('Request info not set');
        abortController.value?.abort();
        abortController.value = new AbortController();
        return await api.artifacts.getList(requestInfo.value.organizationId, requestInfo.value.orbitId, requestInfo.value.collectionId, { cursor, limit, ...sortData.value, types: typesQuery.value }, abortController.value.signal);
    }
    function getNextPageCursor() {
        return savedCursors.value[savedCursors.value.length - 1] ?? null;
    }
    function reset() {
        setList([]);
        savedCursors.value = [];
        requestInfo.value = null;
    }
    function addItemsToList(artifacts) {
        const existingArtifactsIds = list.value.map((artifact) => artifact.id);
        const newArtifacts = artifacts.filter((artifact) => !existingArtifactsIds.includes(artifact.id));
        setList([...list.value, ...newArtifacts]);
    }
    function setSortData(data) {
        sortData.value = data;
    }
    async function onLazyLoad(event) {
        if (isLoading.value)
            return;
        const { last } = event;
        if (last === pageIndex.value * limit) {
            await getNextPage();
        }
    }
    function setList(artifacts) {
        if (syncStore) {
            artifactsStore.setArtifactsList(artifacts);
        }
        else {
            list.value = artifacts;
        }
    }
    async function onSortDataChange() {
        setList([]);
        savedCursors.value = [];
        getInitialPage();
    }
    const debouncedOnSortDataChange = useDebounceFn(onSortDataChange, 500);
    function setLoading(value) {
        isLoading.value = value;
    }
    function setTypesQuery(types) {
        typesQuery.value = types;
    }
    if (syncStore) {
        watch(() => artifactsStore.artifactsList, (storedList) => {
            list.value = storedList;
        }, { immediate: true });
    }
    watch([sortData, typesQuery], debouncedOnSortDataChange);
    return {
        setRequestInfo,
        getInitialPage,
        list,
        getNextPage,
        isLoading,
        pageIndex,
        reset,
        addItemsToList,
        setSortData,
        onLazyLoad,
        setLoading,
        setTypesQuery,
        typesQuery,
    };
};
