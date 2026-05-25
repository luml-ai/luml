import { defineStore } from 'pinia';
import { computed, ref, watch } from 'vue';
import { api } from '@/lib/api';
import { useAuthStore } from './auth';
import { useOrganizationStore } from './organization';
import { useInvitationsStore } from './invitations';
export const useUserStore = defineStore('user', () => {
    const authStore = useAuthStore();
    const invitationsStore = useInvitationsStore();
    const organizationStore = useOrganizationStore();
    const user = ref(null);
    const isPasswordHasBeenChanged = ref(false);
    const getUserEmail = computed(() => user.value?.email);
    const getUserFullName = computed(() => user.value?.full_name);
    const isUserDisabled = computed(() => user.value?.disabled);
    const getUserAvatar = computed(() => user.value?.photo);
    const isUserLoggedWithSSO = computed(() => user.value?.auth_method !== 'email');
    const getUserId = computed(() => user.value?.id);
    const isUserApiKeyExist = computed(() => !!user.value?.has_api_key);
    const loadUser = async () => {
        const data = await api.getMe();
        user.value = data;
    };
    const changePassword = async (data) => {
        await api.updateUser(data);
    };
    const deleteAccount = async () => {
        await api.deleteUser();
        authStore.logout();
    };
    const resetUser = () => {
        user.value = null;
    };
    const resetPassword = async (reset_token, new_password) => {
        return api.resetPassword({ reset_token, new_password });
    };
    const updateUser = async (data) => {
        const response = await api.updateUser(data);
        await loadUser();
        return response;
    };
    const createApiKey = async () => {
        if (!user.value)
            return null;
        const { key } = await api.apiKeys.createApiKey();
        user.value.has_api_key = true;
        return key;
    };
    const deleteApiKey = async () => {
        if (!user.value)
            return;
        await api.apiKeys.deleteApiKey();
        user.value.has_api_key = false;
    };
    watch(() => user.value?.id, async (id) => {
        if (id) {
            await invitationsStore.getInvitations();
            await organizationStore.getAvailableOrganizations();
        }
        else {
            invitationsStore.reset();
            organizationStore.reset();
        }
    });
    return {
        getUserEmail,
        getUserFullName,
        getUserAvatar,
        isUserDisabled,
        isPasswordHasBeenChanged,
        isUserLoggedWithSSO,
        getUserId,
        isUserApiKeyExist,
        loadUser,
        changePassword,
        deleteAccount,
        resetUser,
        resetPassword,
        updateUser,
        createApiKey,
        deleteApiKey,
    };
});
