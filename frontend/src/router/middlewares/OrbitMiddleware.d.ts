import type { NavigationGuardNext, RouteLocationNormalized } from 'vue-router';
export declare function orbitMiddleware(to: RouteLocationNormalized, from: RouteLocationNormalized, next: NavigationGuardNext): Promise<any>;
export declare function setupGuard(to: RouteLocationNormalized, from: RouteLocationNormalized, next: NavigationGuardNext): Promise<any>;
