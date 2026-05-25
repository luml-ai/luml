import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { api } from '@/lib/api';
import { useRoute } from 'vue-router';
import { downloadFileFromBlob } from '@/helpers/helpers';
import axios from 'axios';
export const useArtifactsStore = defineStore('artifacts', () => {
    const route = useRoute();
    const currentArtifact = ref(null);
    const artifactsList = ref([]);
    const setArtifactsList = (list) => {
        artifactsList.value = list;
    };
    function setCurrentArtifact(artifact) {
        currentArtifact.value = artifact;
    }
    function resetCurrentArtifact() {
        currentArtifact.value = null;
    }
    const currentModelTag = ref(null);
    const currentModelMetadata = ref(null);
    const currentModelHtmlBlobUrl = ref(null);
    const experimentSnapshotProvider = ref(null);
    const requestInfo = computed(() => {
        if (typeof route.params.organizationId !== 'string')
            throw new Error('Current organization not found');
        if (typeof route.params.id !== 'string')
            throw new Error('Orbit was not found');
        if (typeof route.params.collectionId !== 'string')
            throw new Error('Collection was not found');
        return {
            organizationId: route.params.organizationId,
            orbitId: route.params.id,
            collectionId: route.params.collectionId,
        };
    });
    function initiateCreateArtifact(data, requestData) {
        const info = requestData ? requestData : requestInfo.value;
        return api.artifacts.create(info.organizationId, info.orbitId, info.collectionId, data);
    }
    async function confirmArtifactUpload(payload, requestData) {
        const info = requestData ? requestData : requestInfo.value;
        const result = await api.artifacts.update(info.organizationId, info.orbitId, info.collectionId, payload.id, payload);
        setArtifactsList([...artifactsList.value, result]);
    }
    async function cancelArtifactUpload(payload, requestData) {
        const info = requestData ? requestData : requestInfo.value;
        await api.artifacts.update(info.organizationId, info.orbitId, info.collectionId, payload.id, payload);
    }
    async function deleteArtifacts(ids) {
        const results = await Promise.allSettled(ids.map((id) => deleteArtifact(id).then(() => id)));
        const deleted = [];
        const failed = [];
        results.forEach((result, index) => {
            if (result.status === 'fulfilled') {
                deleted.push(result.value);
            }
            else {
                failed.push(ids[index]);
            }
        });
        removeArtifactsFromList(deleted);
        return { deleted, failed };
    }
    async function deleteArtifact(id) {
        const { organizationId, orbitId, collectionId } = requestInfo.value;
        const { url } = await api.artifacts.getDeleteUrl(organizationId, orbitId, collectionId, id);
        await axios.delete(url);
        await api.artifacts.confirmDelete(organizationId, orbitId, collectionId, id);
    }
    async function downloadArtifact(id, name) {
        const url = await getDownloadUrl(id);
        const response = await fetch(url);
        const blob = await response.blob();
        downloadFileFromBlob(blob, name);
    }
    async function getDownloadUrl(id) {
        const { organizationId, orbitId, collectionId } = requestInfo.value;
        const { url } = await api.artifacts.getDownloadUrl(organizationId, orbitId, collectionId, id);
        return url;
    }
    function setCurrentModelTag(tag) {
        currentModelTag.value = tag;
    }
    function resetCurrentModelTag() {
        currentModelTag.value = null;
    }
    function setCurrentModelMetadata(metadata) {
        currentModelMetadata.value = metadata;
    }
    function resetCurrentModelMetadata() {
        currentModelMetadata.value = null;
    }
    function setCurrentModelHtmlBlobUrl(htmlFile) {
        currentModelHtmlBlobUrl.value = htmlFile;
    }
    function resetCurrentModelHtmlBlobUrl() {
        currentModelHtmlBlobUrl.value = null;
    }
    function setExperimentSnapshotProvider(provider) {
        experimentSnapshotProvider.value = provider;
    }
    function resetExperimentSnapshotProvider() {
        experimentSnapshotProvider.value = null;
    }
    async function updateArtifact(payload) {
        const { organizationId, orbitId, collectionId } = requestInfo.value;
        const result = await api.artifacts.update(organizationId, orbitId, collectionId, payload.id, payload);
        const newArtifactsList = artifactsList.value.map((a) => (a.id === result.id ? result : a));
        setArtifactsList(newArtifactsList);
        return result;
    }
    async function forceDeleteArtifacts(ids) {
        const { organizationId, orbitId, collectionId } = requestInfo.value;
        const results = await Promise.allSettled(ids.map((id) => api.artifacts.forceDelete(organizationId, orbitId, collectionId, id).then(() => id)));
        const deleted = [];
        const failed = [];
        results.forEach((result, index) => {
            if (result.status === 'fulfilled') {
                deleted.push(result.value);
            }
            else {
                failed.push(ids[index]);
            }
        });
        removeArtifactsFromList(deleted);
        return { deleted, failed };
    }
    async function getArtifactsExtraValues(requestData) {
        const info = requestData ? requestData : requestInfo.value;
        const collectionDetails = await api.orbitCollections.getCollection(info.organizationId, info.orbitId, info.collectionId);
        return collectionDetails.artifacts_extra_values;
    }
    function getArtifact(id, requestData) {
        const info = requestData ? requestData : requestInfo.value;
        const { organizationId, orbitId, collectionId } = info;
        return api.artifacts.getById(organizationId, orbitId, collectionId, id);
    }
    function removeArtifactsFromList(ids) {
        const newArtifactsList = artifactsList.value.filter((a) => !ids.includes(a.id));
        setArtifactsList(newArtifactsList);
    }
    return {
        currentArtifact,
        setCurrentArtifact,
        resetCurrentArtifact,
        requestInfo,
        currentModelTag,
        currentModelMetadata,
        currentModelHtmlBlobUrl,
        experimentSnapshotProvider,
        initiateCreateArtifact,
        confirmArtifactUpload,
        cancelArtifactUpload,
        deleteArtifacts,
        downloadArtifact,
        getDownloadUrl,
        setCurrentModelTag,
        resetCurrentModelTag,
        setCurrentModelMetadata,
        resetCurrentModelMetadata,
        setCurrentModelHtmlBlobUrl,
        resetCurrentModelHtmlBlobUrl,
        setExperimentSnapshotProvider,
        resetExperimentSnapshotProvider,
        updateArtifact,
        forceDeleteArtifacts,
        getArtifactsExtraValues,
        getArtifact,
        artifactsList,
        setArtifactsList,
    };
});
