/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import LayoutHeader from '@/components/layout/LayoutHeader.vue';
import LayoutSidebar from '@/components/layout/LayoutSidebar.vue';
import LayoutFooter from '@/components/layout/LayoutFooter.vue';
import MobileNotAvailablePlug from '@/components/plugs/MobileNotAvailablePlug.vue';
import UiClosablePlug from '@/components/ui/UiClosablePlug.vue';
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { usePlugStore } from '@/stores/plug';
import { useLayout } from '@/hooks/useLayout';
import { useWindowSize } from '@/hooks/useWindowSize';
const router = useRouter();
const route = useRoute();
const plugStore = usePlugStore();
const { headerSizes, sidebarSizes } = useLayout();
const { width: windowWidth } = useWindowSize();
const isBurgerOpen = ref(false);
const isBurgerAvailable = computed(() => windowWidth.value <= 768);
const mobileNotAvailable = computed(() => route.meta.mobileAvailable === false);
const showMobileNotAvailablePlug = computed(() => mobileNotAvailable.value && windowWidth.value <= 768);
const sidebarWidth = computed(() => sidebarSizes.value.width);
router.afterEach(() => {
    isBurgerOpen.value = false;
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['footer']} */ ;
/** @type {__VLS_StyleScopedClasses['page']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "wrapper" },
    ...{ style: ({ paddingLeft: __VLS_ctx.sidebarWidth + 'px', paddingTop: __VLS_ctx.headerSizes.height + 'px' }) },
});
/** @type {__VLS_StyleScopedClasses['wrapper']} */ ;
if (__VLS_ctx.plugStore.visible) {
    const __VLS_0 = UiClosablePlug;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        ...{ 'onClose': {} },
        text: "Some operations may not behave correctly on mobile.",
        ...{ style: ({
                position: 'fixed',
                top: __VLS_ctx.headerSizes.height + 'px',
                left: __VLS_ctx.sidebarSizes.width + 'px',
                right: 0,
                zIndex: 100,
            }) },
    }));
    const __VLS_2 = __VLS_1({
        ...{ 'onClose': {} },
        text: "Some operations may not behave correctly on mobile.",
        ...{ style: ({
                position: 'fixed',
                top: __VLS_ctx.headerSizes.height + 'px',
                left: __VLS_ctx.sidebarSizes.width + 'px',
                right: 0,
                zIndex: 100,
            }) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_5;
    const __VLS_6 = ({ close: {} },
        { onClose: (__VLS_ctx.plugStore.close) });
    var __VLS_3;
    var __VLS_4;
}
const __VLS_7 = LayoutHeader;
// @ts-ignore
const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
    ...{ 'onBurgerClick': {} },
    ...{ class: "header" },
    isBurgerOpen: (__VLS_ctx.isBurgerOpen),
}));
const __VLS_9 = __VLS_8({
    ...{ 'onBurgerClick': {} },
    ...{ class: "header" },
    isBurgerOpen: (__VLS_ctx.isBurgerOpen),
}, ...__VLS_functionalComponentArgsRest(__VLS_8));
let __VLS_12;
const __VLS_13 = ({ burgerClick: {} },
    { onBurgerClick: (() => (__VLS_ctx.isBurgerOpen = !__VLS_ctx.isBurgerOpen)) });
/** @type {__VLS_StyleScopedClasses['header']} */ ;
var __VLS_10;
var __VLS_11;
let __VLS_14;
/** @ts-ignore @type { | typeof __VLS_components.transition | typeof __VLS_components.Transition | typeof __VLS_components.transition | typeof __VLS_components.Transition} */
transition;
// @ts-ignore
const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({}));
const __VLS_16 = __VLS_15({}, ...__VLS_functionalComponentArgsRest(__VLS_15));
const { default: __VLS_19 } = __VLS_17.slots;
const __VLS_20 = LayoutSidebar;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
    ...{ class: "sidebar" },
}));
const __VLS_22 = __VLS_21({
    ...{ class: "sidebar" },
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_asFunctionalDirective(__VLS_directives.vShow, {})(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.isBurgerAvailable ? __VLS_ctx.isBurgerOpen : true) }, null, null);
/** @type {__VLS_StyleScopedClasses['sidebar']} */ ;
// @ts-ignore
[sidebarWidth, headerSizes, headerSizes, plugStore, plugStore, sidebarSizes, isBurgerOpen, isBurgerOpen, isBurgerOpen, isBurgerOpen, isBurgerAvailable,];
var __VLS_17;
const __VLS_25 = LayoutFooter;
// @ts-ignore
const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
    ...{ class: "footer" },
    ...{ style: (`left:${__VLS_ctx.sidebarWidth}px`) },
}));
const __VLS_27 = __VLS_26({
    ...{ class: "footer" },
    ...{ style: (`left:${__VLS_ctx.sidebarWidth}px`) },
}, ...__VLS_functionalComponentArgsRest(__VLS_26));
/** @type {__VLS_StyleScopedClasses['footer']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.main, __VLS_intrinsics.main)({
    ...{ class: "page" },
});
/** @type {__VLS_StyleScopedClasses['page']} */ ;
if (__VLS_ctx.showMobileNotAvailablePlug) {
    const __VLS_30 = MobileNotAvailablePlug;
    // @ts-ignore
    const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({
        ...{ class: "mobile-not-available-plug" },
    }));
    const __VLS_32 = __VLS_31({
        ...{ class: "mobile-not-available-plug" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_31));
    /** @type {__VLS_StyleScopedClasses['mobile-not-available-plug']} */ ;
}
else {
    var __VLS_35 = {};
}
// @ts-ignore
var __VLS_36 = __VLS_35;
// @ts-ignore
[sidebarWidth, showMobileNotAvailablePlug,];
const __VLS_base = (await import('vue')).defineComponent({});
const __VLS_export = {};
export default {};
