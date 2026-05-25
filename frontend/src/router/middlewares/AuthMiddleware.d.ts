import type { NavigationGuardNext, RouteLocationNormalized } from 'vue-router';
export declare function authMiddleware(to: RouteLocationNormalized, from: RouteLocationNormalized, next: NavigationGuardNext): Promise<void>;
