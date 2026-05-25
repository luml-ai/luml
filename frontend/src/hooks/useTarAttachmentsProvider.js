import { ref } from 'vue';
import { TarAttachmentsProvider } from '@luml/attachments';
export function useTarAttachmentsProvider() {
    const provider = ref(null);
    const loading = ref(false);
    const error = ref(null);
    async function init(config) {
        loading.value = true;
        error.value = null;
        try {
            const tarProvider = new TarAttachmentsProvider(config);
            await tarProvider.init();
            provider.value = tarProvider;
        }
        catch (e) {
            console.error('Failed to initialize attachments provider:', e);
            error.value = e instanceof Error ? e.message : 'Unknown error';
            throw e;
        }
        finally {
            loading.value = false;
        }
    }
    return {
        provider,
        loading,
        error,
        init,
    };
}
