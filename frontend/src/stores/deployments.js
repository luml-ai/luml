import { api } from '@/lib/api';
import { defineStore } from 'pinia';
import { ref } from 'vue';
export const useDeploymentsStore = defineStore('deployments', () => {
    const deployments = ref([]);
    const creatorVisible = ref(false);
    async function createDeployment(organizationId, orbitId, payload) {
        const newDeployment = await api.deployments.create(organizationId, orbitId, payload);
        deployments.value.push(newDeployment);
    }
    function getDeployments(organizationId, orbitId) {
        return api.deployments.getList(organizationId, orbitId);
    }
    function setDeployments(data) {
        deployments.value = data;
    }
    function reset() {
        deployments.value = [];
    }
    function showCreator() {
        creatorVisible.value = true;
    }
    function hideCreator() {
        creatorVisible.value = false;
    }
    async function deleteDeployment(organizationId, orbitId, deploymentId) {
        const updatedDeployment = await api.deployments.deleteDeployment(organizationId, orbitId, deploymentId);
        deployments.value = deployments.value.map((deployment) => deployment.id === updatedDeployment.id ? updatedDeployment : deployment);
    }
    async function update(organizationId, orbitId, deploymentId, payload) {
        const newDeployment = await api.deployments.update(organizationId, orbitId, deploymentId, payload);
        deployments.value = deployments.value.map((deployment) => {
            return deployment.id === newDeployment.id ? newDeployment : deployment;
        });
    }
    async function getDeployment(organizationId, orbitId, deploymentId) {
        const existingDeployment = deployments.value.find((deployment) => deployment.id === deploymentId);
        if (existingDeployment) {
            return existingDeployment;
        }
        const deployment = await api.deployments.getDeployment(organizationId, orbitId, deploymentId);
        return deployment;
    }
    async function forceDeleteDeployment(organizationId, orbitId, deploymentId) {
        await api.deployments.forceDeleteDeployment(organizationId, orbitId, deploymentId);
        deployments.value = deployments.value.filter((deployment) => deployment.id !== deploymentId);
    }
    return {
        deployments,
        creatorVisible,
        createDeployment,
        getDeployments,
        setDeployments,
        reset,
        showCreator,
        hideCreator,
        deleteDeployment,
        update,
        getDeployment,
        forceDeleteDeployment,
    };
});
