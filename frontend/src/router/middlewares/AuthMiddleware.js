import { useAuthStore } from '@/stores/auth';
export async function authMiddleware(to, from, next) {
    try {
        const authStore = useAuthStore();
        await authStore.checkIsLoggedIn();
        const isLoggedIn = authStore.isAuth;
        if (to.meta.requireAuth && !isLoggedIn) {
            throw new Error('Login failed');
        }
        else {
            next();
        }
    }
    catch {
        if (to.meta.requireAuth) {
            next({ name: 'home' });
        }
        else {
            next();
        }
    }
}
