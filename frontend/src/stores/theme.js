import { defineStore, storeToRefs } from 'pinia';
import { computed, ref, watch } from 'vue';
import { useAuthStore } from './auth';
export const useThemeStore = defineStore('theme', () => {
    const authStore = useAuthStore();
    const { isAuth } = storeToRefs(authStore);
    const theme = ref('light');
    const getCurrentTheme = computed(() => theme.value);
    const toggleTheme = () => {
        theme.value = theme.value === 'light' ? 'dark' : 'light';
    };
    const changeTheme = () => {
        toggleTheme();
        localStorage.setItem('theme', theme.value);
    };
    const checkTheme = () => {
        const themeInLocalstorage = localStorage.getItem('theme');
        if (themeInLocalstorage && isAuth.value) {
            theme.value = themeInLocalstorage;
        }
        else {
            theme.value = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
                if (!localStorage.getItem('theme'))
                    toggleTheme();
            });
        }
    };
    watch(theme, (t) => {
        document.documentElement.dataset.theme = theme.value;
    });
    watch(isAuth, checkTheme);
    return { getCurrentTheme, changeTheme, checkTheme };
});
