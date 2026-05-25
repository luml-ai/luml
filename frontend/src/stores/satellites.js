import { api } from '@/lib/api';
import { defineStore } from 'pinia';
import { ref } from 'vue';
export const useSatellitesStore = defineStore('satellites', () => {
    const satellitesList = ref([]);
    const creatorVisible = ref(false);
    async function createSatellite(organizationId, orbitId, payload) {
        const data = await api.satellites.create(organizationId, orbitId, payload);
        satellitesList.value.push(data.satellite);
        return data;
    }
    async function loadSatellites(organizationId, orbitId) {
        return api.satellites.getList(organizationId, orbitId);
    }
    function setList(list) {
        satellitesList.value = list;
    }
    async function deleteSatellite(organizationId, orbitId, satelliteId) {
        await api.satellites.delete(organizationId, orbitId, satelliteId);
        setList(satellitesList.value.filter((satellite) => satellite.id !== satelliteId));
    }
    async function updateSatellite(organizationId, orbitId, satelliteId, payload) {
        const newData = await api.satellites.update(organizationId, orbitId, satelliteId, payload);
        const newList = satellitesList.value.map((satellite) => {
            if (satellite.id === newData.id)
                return newData;
            else
                return satellite;
        });
        setList(newList);
    }
    async function regenerateApiKey(organizationId, orbitId, satelliteId) {
        return api.satellites.regenerateApiKye(organizationId, orbitId, satelliteId);
    }
    function showCreator() {
        creatorVisible.value = true;
    }
    function hideCreator() {
        creatorVisible.value = false;
    }
    function reset() {
        satellitesList.value = [];
    }
    async function getSatellite(organizationId, orbitId, satelliteId) {
        const existingSatellite = satellitesList.value.find((satellite) => satellite.id === satelliteId);
        if (existingSatellite) {
            return existingSatellite;
        }
        const satellite = await api.satellites.getItem(organizationId, orbitId, satelliteId);
        return satellite;
    }
    return {
        satellitesList,
        creatorVisible,
        createSatellite,
        loadSatellites,
        setList,
        deleteSatellite,
        updateSatellite,
        regenerateApiKey,
        showCreator,
        hideCreator,
        reset,
        getSatellite,
    };
});
