import { api } from '@/lib/api';
import { ref, watch } from 'vue';
import { useTracksStore } from '@/stores/tracks';
export const useTracksList = (syncStore = true) => {
    const tracksStore = useTracksStore();
    const requestInfo = ref(null);
    const isLoading = ref(false);
    const tracksList = ref([]);
    function setRequestInfo(info) {
        requestInfo.value = info;
    }
    async function load() {
        if (!requestInfo.value)
            throw new Error('Request info not set');
        isLoading.value = true;
        try {
            const response = await api.orbitTracks.listTracks(requestInfo.value.organizationId, requestInfo.value.orbitId);
            setList(response.items);
        }
        finally {
            isLoading.value = false;
        }
    }
    function setList(tracks) {
        if (syncStore) {
            tracksStore.setTracksList(tracks);
        }
        else {
            tracksList.value = tracks;
        }
    }
    function reset() {
        setList([]);
        requestInfo.value = null;
    }
    if (syncStore) {
        watch(() => tracksStore.tracksList, (storeTracksList) => {
            tracksList.value = storeTracksList;
        }, { immediate: true });
    }
    return {
        setRequestInfo,
        load,
        tracksList,
        isLoading,
        reset,
    };
};
