/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import '@scalar/api-reference/style.css';
import { computed, watch } from 'vue';
import { ApiReference } from '@scalar/api-reference';
import { useThemeStore } from '@/stores/theme';
const themeStore = useThemeStore();
const theme = computed(() => themeStore.getCurrentTheme);
const props = defineProps();
const configuration = computed(() => {
    return {
        content: props.content,
        showSidebar: false,
        theme: 'purple',
        hideTestRequestButton: true,
        hideDarkModeToggle: true,
        baseServerURL: 'https://scalar.com',
        showToolbar: 'never',
        servers: [
            {
                url: props.serverUrl,
            },
        ],
    };
});
watch(theme, (t) => {
    setTimeout(() => {
        if (t === 'dark') {
            document.body.classList.add('dark-mode');
            document.body.classList.remove('light-mode');
        }
        else {
            document.body.classList.remove('dark-mode');
            document.body.classList.add('light-mode');
        }
    }, 100);
}, { immediate: true });
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "scalar" },
});
/** @type {__VLS_StyleScopedClasses['scalar']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.ApiReference} */
ApiReference;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ class: "api-reference" },
    configuration: (__VLS_ctx.configuration),
    server: ('http://localhost:8000'),
}));
const __VLS_2 = __VLS_1({
    ...{ class: "api-reference" },
    configuration: (__VLS_ctx.configuration),
    server: ('http://localhost:8000'),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['api-reference']} */ ;
// @ts-ignore
[configuration,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
