import { ref, computed } from 'vue';
import { defineStore } from 'pinia';
import { api } from '@/lib/api';
export const useSecretsStore = defineStore('secrets', () => {
    const secretsList = ref([]);
    const creatorVisible = ref(false);
    const existingTags = computed(() => {
        const tagsSet = secretsList.value.reduce((acc, item) => {
            item.tags?.forEach((tag) => acc.add(tag));
            return acc;
        }, new Set());
        return Array.from(tagsSet);
    });
    function showCreator() {
        creatorVisible.value = true;
    }
    function hideCreator() {
        creatorVisible.value = false;
    }
    async function loadSecrets(organizationId, orbitId) {
        secretsList.value = await api.orbitSecrets.getSecrets(organizationId, orbitId);
    }
    async function addSecret(organizationId, orbitId, payload) {
        await api.orbitSecrets.createSecret(organizationId, orbitId, payload);
        await loadSecrets(organizationId, orbitId);
    }
    async function updateSecret(organizationId, orbitId, payload) {
        await api.orbitSecrets.updateSecret(organizationId, orbitId, payload);
        await loadSecrets(organizationId, orbitId);
    }
    async function deleteSecret(organizationId, orbitId, secretId) {
        await api.orbitSecrets.deleteSecret(organizationId, orbitId, secretId);
        secretsList.value = secretsList.value.filter((secret) => secret.id !== secretId);
    }
    async function getSecretById(organizationId, orbitId, secretId) {
        return await api.orbitSecrets.getSecretById(organizationId, orbitId, secretId);
    }
    function reset() {
        secretsList.value = [];
        creatorVisible.value = false;
    }
    return {
        secretsList,
        creatorVisible,
        existingTags,
        showCreator,
        hideCreator,
        loadSecrets,
        addSecret,
        updateSecret,
        deleteSecret,
        getSecretById,
        reset,
    };
});
