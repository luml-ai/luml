<template>
    <Toast position="top-right" group="toast-link">
        <template #message="slotProps">
            <div class="p-toast-message-content">
                <Check class="p-toast-message-icon" v-if="slotProps.message.severity === 'success'" />
                <div class="p-toast-message-text">
                    <span class="p-toast-summary">{{ slotProps.message.summary }}</span>
                    <div class="p-toast-detail">
                        {{ slotProps.message.detail }}
                        <div v-if="slotProps.message.data?.linkText && slotProps.message.data?.routeName">
                            <a href="#" class="toast-action-link" @click.prevent="handleLink(slotProps)">
                                {{ slotProps.message.data.linkText }}
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </template>
    </Toast>
</template>

<script setup lang="ts">
import Toast from 'primevue/toast';
import { useRouter } from 'vue-router';
import { Check } from 'lucide-vue-next'

const router = useRouter();

function handleLink(slotProps: any) {
    const { data } = slotProps.message;
    if (!data?.routeName) return;
    router.push({ name: data.routeName, params: data.routeParams || {} });
}
</script>

<style scoped>
.toast-action-link {
    display: inline-block;
    margin-top: 0.6rem;
    color: var(--primary-color);
    text-decoration: underline;
    cursor: pointer;
}

.p-toast-message-content {
    display: flex;
    align-items: flex-start;
    padding: 0.25rem 0.5rem 0.25rem 0.5rem;
}

.p-toast-message-text {
    margin: 0;
}

</style>
