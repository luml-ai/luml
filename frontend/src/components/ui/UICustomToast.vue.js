/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import Toast from 'primevue/toast';
import { useRouter } from 'vue-router';
import { Check, Info, AlertTriangle, XCircle } from 'lucide-vue-next';
import DOMPurify from 'dompurify';
const router = useRouter();
function sanitizeDetail(detail) {
    return DOMPurify.sanitize(detail);
}
function handleLinkClick(event) {
    const target = event.target;
    if (target.classList.contains('toast-action-link')) {
        event.preventDefault();
        const routeName = target.getAttribute('data-route');
        const routeParams = target.getAttribute('data-params');
        if (routeName) {
            router.push({
                name: routeName,
                params: routeParams ? JSON.parse(routeParams) : {},
            });
        }
    }
}
function getIconComponent(severity) {
    switch (severity) {
        case 'success':
            return Check;
        case 'info':
            return Info;
        case 'warn':
            return AlertTriangle;
        case 'error':
            return XCircle;
        default:
            return Info;
    }
}
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Toast | typeof __VLS_components.Toast} */
Toast;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    position: "top-right",
}));
const __VLS_2 = __VLS_1({
    position: "top-right",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
const { default: __VLS_6 } = __VLS_3.slots;
{
    const { message: __VLS_7 } = __VLS_3.slots;
    const [slotProps] = __VLS_vSlot(__VLS_7);
    const __VLS_8 = (__VLS_ctx.getIconComponent(slotProps.message.severity));
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
        ...{ class: "p-toast-message-icon" },
    }));
    const __VLS_10 = __VLS_9({
        ...{ class: "p-toast-message-icon" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    /** @type {__VLS_StyleScopedClasses['p-toast-message-icon']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "p-toast-message-text" },
    });
    /** @type {__VLS_StyleScopedClasses['p-toast-message-text']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "p-toast-summary" },
    });
    /** @type {__VLS_StyleScopedClasses['p-toast-summary']} */ ;
    (slotProps.message.summary);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ onClick: (__VLS_ctx.handleLinkClick) },
        ...{ class: "p-toast-detail" },
    });
    __VLS_asFunctionalDirective(__VLS_directives.vHtml, {})(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.sanitizeDetail(slotProps.message.detail)) }, null, null);
    /** @type {__VLS_StyleScopedClasses['p-toast-detail']} */ ;
    // @ts-ignore
    [getIconComponent, handleLinkClick, sanitizeDetail,];
}
// @ts-ignore
[];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
