/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Button, useConfirm, useToast } from 'primevue';
import { LogOut } from 'lucide-vue-next';
import { useOrganizationStore } from '@/stores/organization';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
import { leaveOrganizationConfirmOptions } from '@/lib/primevue/data/confirm';
const props = defineProps();
const confirm = useConfirm();
const organizationStore = useOrganizationStore();
const toast = useToast();
function onClick() {
    confirm.require(leaveOrganizationConfirmOptions(leave));
}
async function leave() {
    try {
        await organizationStore.leaveOrganization(props.organizationId);
        toast.add(simpleSuccessToast('You’ve successfully left the organization.'));
    }
    catch (e) {
        toast.add(simpleErrorToast(e?.response?.data?.detail || 'Failed to log out of the organization'));
    }
}
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    severity: "contrast",
    variant: "text",
    ...{ class: "button" },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    severity: "contrast",
    variant: "text",
    ...{ class: "button" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (__VLS_ctx.onClick) });
var __VLS_7;
/** @type {__VLS_StyleScopedClasses['button']} */ ;
const { default: __VLS_8 } = __VLS_3.slots;
{
    const { icon: __VLS_9 } = __VLS_3.slots;
    let __VLS_10;
    /** @ts-ignore @type { | typeof __VLS_components.LogOut} */
    LogOut;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
        size: (14),
    }));
    const __VLS_12 = __VLS_11({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_11));
    // @ts-ignore
    [onClick,];
}
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
