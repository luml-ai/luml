/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref } from 'vue';
import { Button, Tag } from 'primevue';
import { Play, GitMerge } from 'lucide-vue-next';
import { api } from '@/lib/api';
import { statusSeverity } from './board/board.types';
import MergeDialog from './MergeDialog.vue';
const props = defineProps();
const emit = defineEmits();
const showMerge = ref(false);
async function handleStart() {
    await api.dataAgent.openTerminal(props.task.id);
    emit('refresh');
}
function handleMerged() {
    showMerge.value = false;
    emit('refresh');
}
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
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "task-detail" },
});
/** @type {__VLS_StyleScopedClasses['task-detail']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "header" },
});
/** @type {__VLS_StyleScopedClasses['header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
    ...{ class: "task-title" },
});
/** @type {__VLS_StyleScopedClasses['task-title']} */ ;
(__VLS_ctx.task.name);
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Tag} */
Tag;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    value: (__VLS_ctx.task.status),
    severity: (__VLS_ctx.statusSeverity(__VLS_ctx.task.status)),
}));
const __VLS_2 = __VLS_1({
    value: (__VLS_ctx.task.status),
    severity: (__VLS_ctx.statusSeverity(__VLS_ctx.task.status)),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "actions" },
});
/** @type {__VLS_StyleScopedClasses['actions']} */ ;
if (__VLS_ctx.task.status === 'pending') {
    let __VLS_5;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
        ...{ 'onClick': {} },
        severity: "success",
    }));
    const __VLS_7 = __VLS_6({
        ...{ 'onClick': {} },
        severity: "success",
    }, ...__VLS_functionalComponentArgsRest(__VLS_6));
    let __VLS_10;
    const __VLS_11 = ({ click: {} },
        { onClick: (__VLS_ctx.handleStart) });
    const { default: __VLS_12 } = __VLS_8.slots;
    let __VLS_13;
    /** @ts-ignore @type { | typeof __VLS_components.Play} */
    Play;
    // @ts-ignore
    const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
        size: (14),
    }));
    const __VLS_15 = __VLS_14({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_14));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    // @ts-ignore
    [task, task, task, task, statusSeverity, handleStart,];
    var __VLS_8;
    var __VLS_9;
}
if (__VLS_ctx.task.status === 'succeeded') {
    let __VLS_18;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({
        ...{ 'onClick': {} },
        severity: "success",
    }));
    const __VLS_20 = __VLS_19({
        ...{ 'onClick': {} },
        severity: "success",
    }, ...__VLS_functionalComponentArgsRest(__VLS_19));
    let __VLS_23;
    const __VLS_24 = ({ click: {} },
        { onClick: (...[$event]) => {
                if (!(__VLS_ctx.task.status === 'succeeded'))
                    return;
                __VLS_ctx.showMerge = true;
                // @ts-ignore
                [task, showMerge,];
            } });
    const { default: __VLS_25 } = __VLS_21.slots;
    let __VLS_26;
    /** @ts-ignore @type { | typeof __VLS_components.GitMerge} */
    GitMerge;
    // @ts-ignore
    const __VLS_27 = __VLS_asFunctionalComponent1(__VLS_26, new __VLS_26({
        size: (14),
    }));
    const __VLS_28 = __VLS_27({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_27));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    // @ts-ignore
    [];
    var __VLS_21;
    var __VLS_22;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "info" },
});
/** @type {__VLS_StyleScopedClasses['info']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.strong, __VLS_intrinsics.strong)({});
(__VLS_ctx.task.branch);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.strong, __VLS_intrinsics.strong)({});
(__VLS_ctx.task.agent_id);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.strong, __VLS_intrinsics.strong)({});
(__VLS_ctx.task.worktree_path);
if (__VLS_ctx.task.prompt) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.strong, __VLS_intrinsics.strong)({});
    (__VLS_ctx.task.prompt);
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.strong, __VLS_intrinsics.strong)({});
(__VLS_ctx.task.created_at);
const __VLS_31 = MergeDialog;
// @ts-ignore
const __VLS_32 = __VLS_asFunctionalComponent1(__VLS_31, new __VLS_31({
    ...{ 'onClose': {} },
    ...{ 'onMerged': {} },
    visible: (__VLS_ctx.showMerge),
    kind: "task",
    itemId: (__VLS_ctx.task.id),
}));
const __VLS_33 = __VLS_32({
    ...{ 'onClose': {} },
    ...{ 'onMerged': {} },
    visible: (__VLS_ctx.showMerge),
    kind: "task",
    itemId: (__VLS_ctx.task.id),
}, ...__VLS_functionalComponentArgsRest(__VLS_32));
let __VLS_36;
const __VLS_37 = ({ close: {} },
    { onClose: (...[$event]) => {
            __VLS_ctx.showMerge = false;
            // @ts-ignore
            [task, task, task, task, task, task, task, showMerge, showMerge,];
        } });
const __VLS_38 = ({ merged: {} },
    { onMerged: (__VLS_ctx.handleMerged) });
var __VLS_34;
var __VLS_35;
// @ts-ignore
[handleMerged,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
