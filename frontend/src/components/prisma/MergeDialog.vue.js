/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, watch } from 'vue';
import { Dialog, Button } from 'primevue';
import { Check } from 'lucide-vue-next';
import { api } from '@/lib/api';
const props = defineProps();
const emit = defineEmits();
const preview = ref(null);
const loading = ref(false);
const error = ref('');
const conflictingFiles = ref([]);
watch(() => props.visible, async (isVisible) => {
    if (isVisible) {
        loading.value = true;
        error.value = '';
        try {
            preview.value =
                props.kind === 'task'
                    ? await api.dataAgent.getMergePreview(props.itemId)
                    : await api.dataAgent.getRunMergePreview(props.itemId);
        }
        catch (e) {
            error.value = e?.response?.data?.detail ?? 'Failed to load preview';
        }
        finally {
            loading.value = false;
        }
    }
    else {
        preview.value = null;
    }
});
async function confirmMerge() {
    error.value = '';
    conflictingFiles.value = [];
    try {
        if (props.kind === 'task') {
            await api.dataAgent.mergeTask(props.itemId);
        }
        else {
            await api.dataAgent.mergeRun(props.itemId);
        }
        emit('merged');
    }
    catch (e) {
        const data = e?.response?.data;
        if (e?.response?.status === 409 && data?.conflicting_files) {
            conflictingFiles.value = data.conflicting_files;
            error.value = data.detail ?? 'Merge conflicts detected';
        }
        else {
            error.value = data?.detail ?? 'Merge failed';
        }
    }
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
/** @type {__VLS_StyleScopedClasses['stat-row']} */ ;
/** @type {__VLS_StyleScopedClasses['files']} */ ;
/** @type {__VLS_StyleScopedClasses['files']} */ ;
/** @type {__VLS_StyleScopedClasses['conflict-files']} */ ;
/** @type {__VLS_StyleScopedClasses['conflict-files']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.visible),
    header: (__VLS_ctx.kind === 'task' ? 'Merge Branch' : 'Merge Best Branch'),
    modal: true,
    ...{ style: ({ width: '500px' }) },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.visible),
    header: (__VLS_ctx.kind === 'task' ? 'Merge Branch' : 'Merge Best Branch'),
    modal: true,
    ...{ style: ({ width: '500px' }) },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ 'update:visible': {} },
    { 'onUpdate:visible': (...[$event]) => {
            !$event && __VLS_ctx.emit('close');
            // @ts-ignore
            [visible, kind, emit,];
        } });
var __VLS_7;
const { default: __VLS_8 } = __VLS_3.slots;
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "loading" },
    });
    /** @type {__VLS_StyleScopedClasses['loading']} */ ;
}
else if (__VLS_ctx.preview) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "preview" },
    });
    /** @type {__VLS_StyleScopedClasses['preview']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "branch-block" },
    });
    /** @type {__VLS_StyleScopedClasses['branch-block']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "branch-label" },
    });
    /** @type {__VLS_StyleScopedClasses['branch-label']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.code, __VLS_intrinsics.code)({
        ...{ class: "branch-name" },
    });
    /** @type {__VLS_StyleScopedClasses['branch-name']} */ ;
    (__VLS_ctx.preview.branch);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "branch-block" },
    });
    /** @type {__VLS_StyleScopedClasses['branch-block']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "branch-label" },
    });
    /** @type {__VLS_StyleScopedClasses['branch-label']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.code, __VLS_intrinsics.code)({
        ...{ class: "branch-name" },
    });
    /** @type {__VLS_StyleScopedClasses['branch-name']} */ ;
    (__VLS_ctx.preview.base_branch);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "stats-grid" },
    });
    /** @type {__VLS_StyleScopedClasses['stats-grid']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "stat-row" },
    });
    /** @type {__VLS_StyleScopedClasses['stat-row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.strong, __VLS_intrinsics.strong)({});
    (__VLS_ctx.preview.stats.commits_ahead);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "stat-row" },
    });
    /** @type {__VLS_StyleScopedClasses['stat-row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.strong, __VLS_intrinsics.strong)({});
    (__VLS_ctx.preview.stats.files_changed);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "stat-row" },
    });
    /** @type {__VLS_StyleScopedClasses['stat-row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.strong, __VLS_intrinsics.strong)({
        ...{ class: "ins" },
    });
    /** @type {__VLS_StyleScopedClasses['ins']} */ ;
    (__VLS_ctx.preview.stats.insertions);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "stat-row" },
    });
    /** @type {__VLS_StyleScopedClasses['stat-row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.strong, __VLS_intrinsics.strong)({
        ...{ class: "del" },
    });
    /** @type {__VLS_StyleScopedClasses['del']} */ ;
    (__VLS_ctx.preview.stats.deletions);
    if (__VLS_ctx.preview.can_fast_forward) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "ff-note" },
        });
        /** @type {__VLS_StyleScopedClasses['ff-note']} */ ;
    }
    if (__VLS_ctx.preview.changed_files.length > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "files" },
        });
        /** @type {__VLS_StyleScopedClasses['files']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.strong, __VLS_intrinsics.strong)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({});
        for (const [f] of __VLS_vFor((__VLS_ctx.preview.changed_files))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
                key: (f),
            });
            (f);
            // @ts-ignore
            [loading, preview, preview, preview, preview, preview, preview, preview, preview, preview, preview,];
        }
    }
}
if (__VLS_ctx.error) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "error" },
    });
    /** @type {__VLS_StyleScopedClasses['error']} */ ;
    (__VLS_ctx.error);
    if (__VLS_ctx.conflictingFiles.length > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "conflict-files" },
        });
        /** @type {__VLS_StyleScopedClasses['conflict-files']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.strong, __VLS_intrinsics.strong)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({});
        for (const [f] of __VLS_vFor((__VLS_ctx.conflictingFiles))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
                key: (f),
            });
            (f);
            // @ts-ignore
            [error, error, conflictingFiles, conflictingFiles,];
        }
    }
}
{
    const { footer: __VLS_9 } = __VLS_3.slots;
    let __VLS_10;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
        ...{ 'onClick': {} },
        severity: "secondary",
    }));
    const __VLS_12 = __VLS_11({
        ...{ 'onClick': {} },
        severity: "secondary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_11));
    let __VLS_15;
    const __VLS_16 = ({ click: {} },
        { onClick: (...[$event]) => {
                __VLS_ctx.emit('close');
                // @ts-ignore
                [emit,];
            } });
    const { default: __VLS_17 } = __VLS_13.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    // @ts-ignore
    [];
    var __VLS_13;
    var __VLS_14;
    let __VLS_18;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({
        ...{ 'onClick': {} },
        disabled: (!__VLS_ctx.preview),
    }));
    const __VLS_20 = __VLS_19({
        ...{ 'onClick': {} },
        disabled: (!__VLS_ctx.preview),
    }, ...__VLS_functionalComponentArgsRest(__VLS_19));
    let __VLS_23;
    const __VLS_24 = ({ click: {} },
        { onClick: (__VLS_ctx.confirmMerge) });
    const { default: __VLS_25 } = __VLS_21.slots;
    let __VLS_26;
    /** @ts-ignore @type { | typeof __VLS_components.Check} */
    Check;
    // @ts-ignore
    const __VLS_27 = __VLS_asFunctionalComponent1(__VLS_26, new __VLS_26({
        size: (14),
    }));
    const __VLS_28 = __VLS_27({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_27));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    // @ts-ignore
    [preview, confirmMerge,];
    var __VLS_21;
    var __VLS_22;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
