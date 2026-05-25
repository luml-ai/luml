/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import GoogleIcon from '@/assets/img/authorization-services/google.svg';
import MicrosoftIcon from '@/assets/img/authorization-services/microsoft.svg';
// import GitHubIcon from '@/assets/img/authorization-services/github.svg'
import { useAuthStore } from '@/stores/auth';
import { useUserStore } from '@/stores/user';
import { onBeforeMount, ref } from 'vue';
import { useRouter } from 'vue-router';
const authStore = useAuthStore();
const userStore = useUserStore();
const router = useRouter();
const __VLS_props = defineProps();
const servicesError = ref('');
const services = [
    {
        id: 'google',
        label: 'Sign in with Google',
        icon: GoogleIcon,
        action: () => (window.location.href = `${import.meta.env.VITE_API_URL}/v1/auth/google/login`),
    },
    {
        id: 'microsoft',
        label: 'Sign in with Microsoft',
        icon: MicrosoftIcon,
        action: () => (window.location.href = `${import.meta.env.VITE_API_URL}/v1/auth/microsoft/login`),
    },
    // {
    //   id: 'github',
    //   label: 'Sign in with Github',
    //   icon: GitHubIcon,
    //   action: () => console.log('Github'),
    // },
];
onBeforeMount(async () => {
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');
    const provider = urlParams.get('state');
    if (!code)
        return;
    try {
        if (provider === 'google') {
            await authStore.loginWithGoogle(code);
        }
        else if (provider === 'microsoft') {
            await authStore.loginWithMicrosoft(code);
        }
        await userStore.loadUser();
        router.push({ name: 'home' });
    }
    catch (e) {
        console.error(e);
    }
});
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['form-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['button-plain']} */ ;
/** @type {__VLS_StyleScopedClasses['button-plain']} */ ;
/** @type {__VLS_StyleScopedClasses['wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['body']} */ ;
/** @type {__VLS_StyleScopedClasses['body']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "wrapper" },
});
/** @type {__VLS_StyleScopedClasses['wrapper']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "body" },
});
/** @type {__VLS_StyleScopedClasses['body']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "content" },
});
/** @type {__VLS_StyleScopedClasses['content']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "headings" },
});
/** @type {__VLS_StyleScopedClasses['headings']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({
    ...{ class: "main-title" },
});
/** @type {__VLS_StyleScopedClasses['main-title']} */ ;
(__VLS_ctx.title);
if (__VLS_ctx.subTitle) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
        ...{ class: "sub-title" },
    });
    /** @type {__VLS_StyleScopedClasses['sub-title']} */ ;
    (__VLS_ctx.subTitle);
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "form-wrapper" },
});
/** @type {__VLS_StyleScopedClasses['form-wrapper']} */ ;
var __VLS_0 = {};
if (__VLS_ctx.services && !__VLS_ctx.hideSso) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "line" },
    });
    /** @type {__VLS_StyleScopedClasses['line']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "services" },
    });
    /** @type {__VLS_StyleScopedClasses['services']} */ ;
    for (const [service] of __VLS_vFor((__VLS_ctx.services))) {
        let __VLS_2;
        /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
        dButton;
        // @ts-ignore
        const __VLS_3 = __VLS_asFunctionalComponent1(__VLS_2, new __VLS_2({
            ...{ 'onClick': {} },
            key: (service.id),
            variant: "outlined",
            ...{ class: "button-plain" },
            link: true,
        }));
        const __VLS_4 = __VLS_3({
            ...{ 'onClick': {} },
            key: (service.id),
            variant: "outlined",
            ...{ class: "button-plain" },
            link: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_3));
        let __VLS_7;
        const __VLS_8 = ({ click: {} },
            { onClick: (() => service.action()) });
        /** @type {__VLS_StyleScopedClasses['button-plain']} */ ;
        const { default: __VLS_9 } = __VLS_5.slots;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "service-label" },
        });
        /** @type {__VLS_StyleScopedClasses['service-label']} */ ;
        (service.label);
        __VLS_asFunctionalElement1(__VLS_intrinsics.img)({
            src: (service.icon),
            alt: "",
            width: "24",
            height: "24",
            ...{ class: "icon" },
        });
        /** @type {__VLS_StyleScopedClasses['icon']} */ ;
        // @ts-ignore
        [title, subTitle, subTitle, services, services, hideSso,];
        var __VLS_5;
        var __VLS_6;
        // @ts-ignore
        [];
    }
    if (__VLS_ctx.servicesError) {
        let __VLS_10;
        /** @ts-ignore @type { | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message'] | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message']} */
        dMessage;
        // @ts-ignore
        const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
            severity: "error",
            size: "small",
            variant: "simple",
        }));
        const __VLS_12 = __VLS_11({
            severity: "error",
            size: "small",
            variant: "simple",
        }, ...__VLS_functionalComponentArgsRest(__VLS_11));
        const { default: __VLS_15 } = __VLS_13.slots;
        (__VLS_ctx.servicesError);
        // @ts-ignore
        [servicesError, servicesError,];
        var __VLS_13;
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "footer" },
});
/** @type {__VLS_StyleScopedClasses['footer']} */ ;
var __VLS_16 = {};
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "image" },
});
/** @type {__VLS_StyleScopedClasses['image']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.img)({
    src: (__VLS_ctx.image),
    alt: "LUML",
    ...{ class: "img" },
});
/** @type {__VLS_StyleScopedClasses['img']} */ ;
// @ts-ignore
var __VLS_1 = __VLS_0, __VLS_17 = __VLS_16;
// @ts-ignore
[image,];
const __VLS_base = (await import('vue')).defineComponent({
    __typeProps: {},
});
const __VLS_export = {};
export default {};
