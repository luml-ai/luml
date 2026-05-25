/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import AuthorizationWrapper from '@/components/authorization/AuthorizationWrapper.vue';
import MainImage from '@/assets/img/form-bg.webp';
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
const __VLS_0 = AuthorizationWrapper || AuthorizationWrapper;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    title: "Email confirmed!",
    subTitle: "Thank you for verifying your email address. Your account is now fully activated, and you can proceed to access all the features of our platform.",
    image: (__VLS_ctx.MainImage),
    hideSso: (true),
}));
const __VLS_2 = __VLS_1({
    title: "Email confirmed!",
    subTitle: "Thank you for verifying your email address. Your account is now fully activated, and you can proceed to access all the features of our platform.",
    image: (__VLS_ctx.MainImage),
    hideSso: (true),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
const { default: __VLS_6 } = __VLS_3.slots;
{
    const { form: __VLS_7 } = __VLS_3.slots;
    let __VLS_8;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
        ...{ 'onClick': {} },
        type: "submit",
        label: "Go to account",
        rounded: true,
        fluid: true,
    }));
    const __VLS_10 = __VLS_9({
        ...{ 'onClick': {} },
        type: "submit",
        label: "Go to account",
        rounded: true,
        fluid: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    let __VLS_13;
    const __VLS_14 = ({ click: {} },
        { onClick: (...[$event]) => {
                __VLS_ctx.$router.push({ name: 'sign-in' });
                // @ts-ignore
                [MainImage, $router,];
            } });
    var __VLS_11;
    var __VLS_12;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
