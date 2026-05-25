/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import UserToolbar from '../user/UserToolbar.vue';
import { useAuthStore } from '@/stores/auth';
import { X, Menu } from 'lucide-vue-next';
import OrganizationManagePopover from '../organizations/OrganizationManagePopover.vue';
import OrbitManagePopover from '../orbits/OrbitManagePopover.vue';
const __VLS_props = defineProps({
    isActivesVisible: {
        type: Boolean,
        default: true,
    },
    isBurgerOpen: {
        type: Boolean,
    },
});
const __VLS_emit = defineEmits();
const authStore = useAuthStore();
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['header']} */ ;
/** @type {__VLS_StyleScopedClasses['logo-group']} */ ;
/** @type {__VLS_StyleScopedClasses['burger-button']} */ ;
/** @type {__VLS_StyleScopedClasses['logo-dark']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
    id: "header",
    ...{ class: "header" },
});
/** @type {__VLS_StyleScopedClasses['header']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.routerLink | typeof __VLS_components.RouterLink | typeof __VLS_components['router-link'] | typeof __VLS_components.routerLink | typeof __VLS_components.RouterLink | typeof __VLS_components['router-link']} */
routerLink;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    to: ({ name: 'home' }),
    ...{ class: "logo" },
}));
const __VLS_2 = __VLS_1({
    to: ({ name: 'home' }),
    ...{ class: "logo" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['logo']} */ ;
const { default: __VLS_5 } = __VLS_3.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.img)({
    src: "@/assets/img/Logo_Full_light_mode.svg",
    alt: "LUML",
    ...{ class: "logo-img logo-light" },
});
/** @type {__VLS_StyleScopedClasses['logo-img']} */ ;
/** @type {__VLS_StyleScopedClasses['logo-light']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.img)({
    src: "@/assets/img/Logo_Full_dark_mode.svg",
    alt: "LUML",
    ...{ class: "logo-img logo-dark" },
});
/** @type {__VLS_StyleScopedClasses['logo-img']} */ ;
/** @type {__VLS_StyleScopedClasses['logo-dark']} */ ;
var __VLS_3;
if (__VLS_ctx.authStore.isAuth) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "logo-group" },
    });
    /** @type {__VLS_StyleScopedClasses['logo-group']} */ ;
    const __VLS_6 = OrganizationManagePopover;
    // @ts-ignore
    const __VLS_7 = __VLS_asFunctionalComponent1(__VLS_6, new __VLS_6({}));
    const __VLS_8 = __VLS_7({}, ...__VLS_functionalComponentArgsRest(__VLS_7));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "separator" },
    });
    /** @type {__VLS_StyleScopedClasses['separator']} */ ;
    const __VLS_11 = OrbitManagePopover;
    // @ts-ignore
    const __VLS_12 = __VLS_asFunctionalComponent1(__VLS_11, new __VLS_11({}));
    const __VLS_13 = __VLS_12({}, ...__VLS_functionalComponentArgsRest(__VLS_12));
}
if (__VLS_ctx.isActivesVisible) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "actives" },
    });
    /** @type {__VLS_StyleScopedClasses['actives']} */ ;
    if (__VLS_ctx.authStore.isAuth) {
        const __VLS_16 = UserToolbar;
        // @ts-ignore
        const __VLS_17 = __VLS_asFunctionalComponent1(__VLS_16, new __VLS_16({}));
        const __VLS_18 = __VLS_17({}, ...__VLS_functionalComponentArgsRest(__VLS_17));
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "buttons" },
        });
        /** @type {__VLS_StyleScopedClasses['buttons']} */ ;
        let __VLS_21;
        /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
        dButton;
        // @ts-ignore
        const __VLS_22 = __VLS_asFunctionalComponent1(__VLS_21, new __VLS_21({
            ...{ 'onClick': {} },
            label: "Log in",
            severity: "contrast",
            variant: "text",
        }));
        const __VLS_23 = __VLS_22({
            ...{ 'onClick': {} },
            label: "Log in",
            severity: "contrast",
            variant: "text",
        }, ...__VLS_functionalComponentArgsRest(__VLS_22));
        let __VLS_26;
        const __VLS_27 = ({ click: {} },
            { onClick: (...[$event]) => {
                    if (!(__VLS_ctx.isActivesVisible))
                        return;
                    if (!!(__VLS_ctx.authStore.isAuth))
                        return;
                    __VLS_ctx.$router.push({ name: 'sign-in', query: { redirect: __VLS_ctx.$route.fullPath } });
                    // @ts-ignore
                    [authStore, authStore, isActivesVisible, $router, $route,];
                } });
        var __VLS_24;
        var __VLS_25;
        let __VLS_28;
        /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
        dButton;
        // @ts-ignore
        const __VLS_29 = __VLS_asFunctionalComponent1(__VLS_28, new __VLS_28({
            ...{ 'onClick': {} },
            ...{ class: "sign-up-button" },
            label: "Sign up",
            severity: "primary",
            variant: "text",
        }));
        const __VLS_30 = __VLS_29({
            ...{ 'onClick': {} },
            ...{ class: "sign-up-button" },
            label: "Sign up",
            severity: "primary",
            variant: "text",
        }, ...__VLS_functionalComponentArgsRest(__VLS_29));
        let __VLS_33;
        const __VLS_34 = ({ click: {} },
            { onClick: (...[$event]) => {
                    if (!(__VLS_ctx.isActivesVisible))
                        return;
                    if (!!(__VLS_ctx.authStore.isAuth))
                        return;
                    __VLS_ctx.$router.push({ name: 'sign-up', query: { redirect: __VLS_ctx.$route.fullPath } });
                    // @ts-ignore
                    [$router, $route,];
                } });
        /** @type {__VLS_StyleScopedClasses['sign-up-button']} */ ;
        var __VLS_31;
        var __VLS_32;
    }
    let __VLS_35;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_36 = __VLS_asFunctionalComponent1(__VLS_35, new __VLS_35({
        ...{ 'onClick': {} },
        ...{ class: "burger-button" },
        variant: "text",
        severity: "contrast",
    }));
    const __VLS_37 = __VLS_36({
        ...{ 'onClick': {} },
        ...{ class: "burger-button" },
        variant: "text",
        severity: "contrast",
    }, ...__VLS_functionalComponentArgsRest(__VLS_36));
    let __VLS_40;
    const __VLS_41 = ({ click: {} },
        { onClick: (...[$event]) => {
                if (!(__VLS_ctx.isActivesVisible))
                    return;
                __VLS_ctx.$emit('burgerClick');
                // @ts-ignore
                [$emit,];
            } });
    /** @type {__VLS_StyleScopedClasses['burger-button']} */ ;
    const { default: __VLS_42 } = __VLS_38.slots;
    {
        const { icon: __VLS_43 } = __VLS_38.slots;
        let __VLS_44;
        /** @ts-ignore @type { | typeof __VLS_components.transition | typeof __VLS_components.Transition | typeof __VLS_components.transition | typeof __VLS_components.Transition} */
        transition;
        // @ts-ignore
        const __VLS_45 = __VLS_asFunctionalComponent1(__VLS_44, new __VLS_44({}));
        const __VLS_46 = __VLS_45({}, ...__VLS_functionalComponentArgsRest(__VLS_45));
        const { default: __VLS_49 } = __VLS_47.slots;
        if (__VLS_ctx.isBurgerOpen) {
            let __VLS_50;
            /** @ts-ignore @type { | typeof __VLS_components.X} */
            X;
            // @ts-ignore
            const __VLS_51 = __VLS_asFunctionalComponent1(__VLS_50, new __VLS_50({
                size: (24),
            }));
            const __VLS_52 = __VLS_51({
                size: (24),
            }, ...__VLS_functionalComponentArgsRest(__VLS_51));
        }
        else {
            let __VLS_55;
            /** @ts-ignore @type { | typeof __VLS_components.Menu} */
            Menu;
            // @ts-ignore
            const __VLS_56 = __VLS_asFunctionalComponent1(__VLS_55, new __VLS_55({
                size: (24),
            }));
            const __VLS_57 = __VLS_56({
                size: (24),
            }, ...__VLS_functionalComponentArgsRest(__VLS_56));
        }
        // @ts-ignore
        [isBurgerOpen,];
        var __VLS_47;
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
    var __VLS_38;
    var __VLS_39;
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    props: {
        isActivesVisible: {
            type: Boolean,
            default: true,
        },
        isBurgerOpen: {
            type: Boolean,
        },
    },
});
export default {};
