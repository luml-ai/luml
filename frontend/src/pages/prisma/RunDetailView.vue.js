/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { Button, Tag, Dialog, Message } from 'primevue';
import { ArrowLeft, Play, X, GitMerge, RefreshCw } from 'lucide-vue-next';
import { api } from '@/lib/api';
import { usePrismaStore } from '@/stores/prisma';
import { useUploadFlow } from '@/hooks/useUploadFlow';
import { useAgentWebSocket } from '@/hooks/useAgentWebSocket';
import { statusSeverity } from '@/components/prisma/board/board.types';
import RunGraph from '@/components/prisma/RunGraph.vue';
import NodeDetail from '@/components/prisma/NodeDetail.vue';
import TerminalPanel from '@/components/prisma/TerminalPanel.vue';
import MergeDialog from '@/components/prisma/MergeDialog.vue';
const route = useRoute();
const router = useRouter();
const store = usePrismaStore();
const uploadFlow = useUploadFlow();
const terminalSessionId = ref(null);
const terminalLabel = ref('Terminal');
const terminalReadonly = ref(false);
const showTerminal = ref(false);
const showMergeDialog = ref(false);
const nodeArtifact = computed(() => {
    const nodeId = store.selectedNode?.id;
    if (!nodeId)
        return undefined;
    return uploadFlow.getNodeArtifact(nodeId);
});
const canMerge = computed(() => {
    const run = store.selectedRun;
    return run && run.status === 'succeeded' && run.best_node_id;
});
const bestScore = computed(() => {
    const run = store.selectedRun;
    if (!run?.best_node_id)
        return null;
    const bestNode = store.nodes.find((n) => n.id === run.best_node_id);
    if (!bestNode)
        return null;
    const metric = bestNode.result?.artifacts?.metric;
    if (metric === undefined || metric === null)
        return null;
    if (typeof metric === 'number') {
        return Number.isInteger(metric) ? String(metric) : metric.toFixed(4);
    }
    return String(metric);
});
const initialId = String(route.params.runId || '');
if (initialId) {
    store.selectRun(initialId);
}
useAgentWebSocket(uploadFlow);
async function loadInitialData() {
    const id = String(route.params.runId || '');
    if (!id)
        return;
    store.selectRun(id);
    try {
        const [graph, run] = await Promise.all([
            api.dataAgent.getRunGraph(id),
            api.dataAgent.getRun(id),
        ]);
        store.updateRun(run);
        store.applySnapshot({ ...graph, run });
        const config = run.config;
        if (config.luml_collection_id && config.luml_organization_id && config.luml_orbit_id) {
            uploadFlow.resumePendingUploads(id, config.luml_collection_id, config.luml_organization_id, config.luml_orbit_id);
        }
    }
    catch {
        // WS will provide data
    }
}
function onRetryUpload(uploadId) {
    const run = store.selectedRun;
    if (!run?.config.luml_collection_id)
        return;
    const entry = uploadFlow.uploads.value.get(uploadId);
    if (!entry)
        return;
    const event = {
        upload_id: uploadId,
        run_id: entry.runId,
        node_id: entry.nodeId,
        file_size: 0,
        experiment_ids: [],
        collection_id: run.config.luml_collection_id,
        organization_id: run.config.luml_organization_id,
        orbit_id: run.config.luml_orbit_id,
        manifest: {},
        file_index: {},
    };
    uploadFlow.retryUpload(uploadId, event);
}
async function onStartRun() {
    const run = await api.dataAgent.startRun(store.selectedRunId);
    store.updateRun(run);
}
async function onCancelRun() {
    const run = await api.dataAgent.cancelRun(store.selectedRunId);
    store.updateRun(run);
}
async function onMerged() {
    showMergeDialog.value = false;
    const run = await api.dataAgent.getRun(store.selectedRunId);
    store.updateRun(run);
}
function openTerminalDialog(sessionId, label, readonly = false) {
    terminalSessionId.value = sessionId;
    terminalLabel.value = label ?? 'Terminal';
    terminalReadonly.value = readonly;
    showTerminal.value = true;
}
function closeTerminal() {
    showTerminal.value = false;
    terminalSessionId.value = null;
}
function onAttachTerminal(sessionId, readonly = false) {
    const node = store.selectedNode;
    const label = node ? `${node.node_type} #${node.id}` : 'Terminal';
    openTerminalDialog(sessionId, label, readonly);
}
function onGraphOpenTerminal(sessionId, label) {
    openTerminalDialog(sessionId, label);
}
function closeNodeDetail() {
    store.selectNode(null);
}
function goBack() {
    router.push({ name: 'prisma-board' });
}
onMounted(() => {
    loadInitialData();
});
onUnmounted(() => {
    store.selectRun(null);
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['upload-banner']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "run-detail-view" },
});
/** @type {__VLS_StyleScopedClasses['run-detail-view']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "detail-content" },
});
/** @type {__VLS_StyleScopedClasses['detail-content']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "content-header" },
});
/** @type {__VLS_StyleScopedClasses['content-header']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    variant: "text",
    severity: "secondary",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    variant: "text",
    severity: "secondary",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (__VLS_ctx.goBack) });
const { default: __VLS_7 } = __VLS_3.slots;
{
    const { icon: __VLS_8 } = __VLS_3.slots;
    let __VLS_9;
    /** @ts-ignore @type { | typeof __VLS_components.ArrowLeft} */
    ArrowLeft;
    // @ts-ignore
    const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
        size: (16),
    }));
    const __VLS_11 = __VLS_10({
        size: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_10));
    // @ts-ignore
    [goBack,];
}
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
if (__VLS_ctx.store.selectedRun) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "header-info" },
    });
    /** @type {__VLS_StyleScopedClasses['header-info']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "header-info-top" },
    });
    /** @type {__VLS_StyleScopedClasses['header-info-top']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "content-title" },
    });
    /** @type {__VLS_StyleScopedClasses['content-title']} */ ;
    (__VLS_ctx.store.selectedRun.name);
    let __VLS_14;
    /** @ts-ignore @type { | typeof __VLS_components.Tag} */
    Tag;
    // @ts-ignore
    const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
        value: (__VLS_ctx.store.selectedRun.status),
        severity: (__VLS_ctx.statusSeverity(__VLS_ctx.store.selectedRun.status)),
    }));
    const __VLS_16 = __VLS_15({
        value: (__VLS_ctx.store.selectedRun.status),
        severity: (__VLS_ctx.statusSeverity(__VLS_ctx.store.selectedRun.status)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_15));
    if (__VLS_ctx.bestScore) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "best-score-label" },
        });
        /** @type {__VLS_StyleScopedClasses['best-score-label']} */ ;
        (__VLS_ctx.bestScore);
    }
    if (__VLS_ctx.store.selectedRun.objective) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "run-objective" },
        });
        /** @type {__VLS_StyleScopedClasses['run-objective']} */ ;
        (__VLS_ctx.store.selectedRun.objective);
    }
    if (__VLS_ctx.store.selectedRun.status === 'pending') {
        let __VLS_19;
        /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
            ...{ 'onClick': {} },
            severity: "success",
        }));
        const __VLS_21 = __VLS_20({
            ...{ 'onClick': {} },
            severity: "success",
        }, ...__VLS_functionalComponentArgsRest(__VLS_20));
        let __VLS_24;
        const __VLS_25 = ({ click: {} },
            { onClick: (__VLS_ctx.onStartRun) });
        const { default: __VLS_26 } = __VLS_22.slots;
        let __VLS_27;
        /** @ts-ignore @type { | typeof __VLS_components.Play} */
        Play;
        // @ts-ignore
        const __VLS_28 = __VLS_asFunctionalComponent1(__VLS_27, new __VLS_27({
            size: (14),
        }));
        const __VLS_29 = __VLS_28({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_28));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        // @ts-ignore
        [store, store, store, store, store, store, store, statusSeverity, bestScore, bestScore, onStartRun,];
        var __VLS_22;
        var __VLS_23;
    }
    if (__VLS_ctx.store.selectedRun.status === 'running') {
        let __VLS_32;
        /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_33 = __VLS_asFunctionalComponent1(__VLS_32, new __VLS_32({
            ...{ 'onClick': {} },
            severity: "warn",
        }));
        const __VLS_34 = __VLS_33({
            ...{ 'onClick': {} },
            severity: "warn",
        }, ...__VLS_functionalComponentArgsRest(__VLS_33));
        let __VLS_37;
        const __VLS_38 = ({ click: {} },
            { onClick: (__VLS_ctx.onCancelRun) });
        const { default: __VLS_39 } = __VLS_35.slots;
        let __VLS_40;
        /** @ts-ignore @type { | typeof __VLS_components.X} */
        X;
        // @ts-ignore
        const __VLS_41 = __VLS_asFunctionalComponent1(__VLS_40, new __VLS_40({
            size: (14),
        }));
        const __VLS_42 = __VLS_41({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_41));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        // @ts-ignore
        [store, onCancelRun,];
        var __VLS_35;
        var __VLS_36;
    }
    if (__VLS_ctx.canMerge) {
        let __VLS_45;
        /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_46 = __VLS_asFunctionalComponent1(__VLS_45, new __VLS_45({
            ...{ 'onClick': {} },
            severity: "success",
        }));
        const __VLS_47 = __VLS_46({
            ...{ 'onClick': {} },
            severity: "success",
        }, ...__VLS_functionalComponentArgsRest(__VLS_46));
        let __VLS_50;
        const __VLS_51 = ({ click: {} },
            { onClick: (...[$event]) => {
                    if (!(__VLS_ctx.store.selectedRun))
                        return;
                    if (!(__VLS_ctx.canMerge))
                        return;
                    __VLS_ctx.showMergeDialog = true;
                    // @ts-ignore
                    [canMerge, showMergeDialog,];
                } });
        const { default: __VLS_52 } = __VLS_48.slots;
        let __VLS_53;
        /** @ts-ignore @type { | typeof __VLS_components.GitMerge} */
        GitMerge;
        // @ts-ignore
        const __VLS_54 = __VLS_asFunctionalComponent1(__VLS_53, new __VLS_53({
            size: (14),
        }));
        const __VLS_55 = __VLS_54({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_54));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        // @ts-ignore
        [];
        var __VLS_48;
        var __VLS_49;
    }
}
if (__VLS_ctx.uploadFlow.worktreesPendingMessage.value) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "upload-banner" },
    });
    /** @type {__VLS_StyleScopedClasses['upload-banner']} */ ;
    let __VLS_58;
    /** @ts-ignore @type { | typeof __VLS_components.Message | typeof __VLS_components.Message} */
    Message;
    // @ts-ignore
    const __VLS_59 = __VLS_asFunctionalComponent1(__VLS_58, new __VLS_58({
        severity: "info",
        closable: (false),
    }));
    const __VLS_60 = __VLS_59({
        severity: "info",
        closable: (false),
    }, ...__VLS_functionalComponentArgsRest(__VLS_59));
    const { default: __VLS_63 } = __VLS_61.slots;
    (__VLS_ctx.uploadFlow.worktreesPendingMessage.value);
    // @ts-ignore
    [uploadFlow, uploadFlow,];
    var __VLS_61;
}
for (const [entry] of __VLS_vFor((__VLS_ctx.uploadFlow.failedUploads.value))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        key: (entry.uploadId),
        ...{ class: "upload-banner" },
    });
    /** @type {__VLS_StyleScopedClasses['upload-banner']} */ ;
    let __VLS_64;
    /** @ts-ignore @type { | typeof __VLS_components.Message | typeof __VLS_components.Message} */
    Message;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent1(__VLS_64, new __VLS_64({
        severity: "error",
        closable: (false),
    }));
    const __VLS_66 = __VLS_65({
        severity: "error",
        closable: (false),
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    const { default: __VLS_69 } = __VLS_67.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    (entry.nodeId);
    (entry.error);
    let __VLS_70;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_71 = __VLS_asFunctionalComponent1(__VLS_70, new __VLS_70({
        ...{ 'onClick': {} },
        size: "small",
        severity: "secondary",
        text: true,
    }));
    const __VLS_72 = __VLS_71({
        ...{ 'onClick': {} },
        size: "small",
        severity: "secondary",
        text: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_71));
    let __VLS_75;
    const __VLS_76 = ({ click: {} },
        { onClick: (...[$event]) => {
                __VLS_ctx.onRetryUpload(entry.uploadId);
                // @ts-ignore
                [uploadFlow, onRetryUpload,];
            } });
    const { default: __VLS_77 } = __VLS_73.slots;
    let __VLS_78;
    /** @ts-ignore @type { | typeof __VLS_components.RefreshCw} */
    RefreshCw;
    // @ts-ignore
    const __VLS_79 = __VLS_asFunctionalComponent1(__VLS_78, new __VLS_78({
        size: (12),
    }));
    const __VLS_80 = __VLS_79({
        size: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_79));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    // @ts-ignore
    [];
    var __VLS_73;
    var __VLS_74;
    // @ts-ignore
    [];
    var __VLS_67;
    // @ts-ignore
    [];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "graph-area" },
});
/** @type {__VLS_StyleScopedClasses['graph-area']} */ ;
if (__VLS_ctx.store.selectedRunId) {
    const __VLS_83 = RunGraph;
    // @ts-ignore
    const __VLS_84 = __VLS_asFunctionalComponent1(__VLS_83, new __VLS_83({
        ...{ 'onOpenTerminal': {} },
    }));
    const __VLS_85 = __VLS_84({
        ...{ 'onOpenTerminal': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_84));
    let __VLS_88;
    const __VLS_89 = ({ openTerminal: {} },
        { onOpenTerminal: (__VLS_ctx.onGraphOpenTerminal) });
    var __VLS_86;
    var __VLS_87;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "graph-loading" },
    });
    /** @type {__VLS_StyleScopedClasses['graph-loading']} */ ;
}
let __VLS_90;
/** @ts-ignore @type { | typeof __VLS_components.Transition | typeof __VLS_components.Transition} */
Transition;
// @ts-ignore
const __VLS_91 = __VLS_asFunctionalComponent1(__VLS_90, new __VLS_90({
    name: "slide-right",
}));
const __VLS_92 = __VLS_91({
    name: "slide-right",
}, ...__VLS_functionalComponentArgsRest(__VLS_91));
const { default: __VLS_95 } = __VLS_93.slots;
let __VLS_96;
/** @ts-ignore @type { | typeof __VLS_components.Teleport | typeof __VLS_components.Teleport} */
Teleport;
// @ts-ignore
const __VLS_97 = __VLS_asFunctionalComponent1(__VLS_96, new __VLS_96({
    to: "body",
}));
const __VLS_98 = __VLS_97({
    to: "body",
}, ...__VLS_functionalComponentArgsRest(__VLS_97));
const { default: __VLS_101 } = __VLS_99.slots;
if (__VLS_ctx.store.selectedNodeId) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ onClick: (__VLS_ctx.closeNodeDetail) },
        ...{ class: "sidebar-wrapper" },
    });
    /** @type {__VLS_StyleScopedClasses['sidebar-wrapper']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "node-sidebar" },
    });
    /** @type {__VLS_StyleScopedClasses['node-sidebar']} */ ;
    const __VLS_102 = NodeDetail;
    // @ts-ignore
    const __VLS_103 = __VLS_asFunctionalComponent1(__VLS_102, new __VLS_102({
        ...{ 'onAttachTerminal': {} },
        ...{ 'onClose': {} },
        artifact: (__VLS_ctx.nodeArtifact),
    }));
    const __VLS_104 = __VLS_103({
        ...{ 'onAttachTerminal': {} },
        ...{ 'onClose': {} },
        artifact: (__VLS_ctx.nodeArtifact),
    }, ...__VLS_functionalComponentArgsRest(__VLS_103));
    let __VLS_107;
    const __VLS_108 = ({ attachTerminal: {} },
        { onAttachTerminal: (__VLS_ctx.onAttachTerminal) });
    const __VLS_109 = ({ close: {} },
        { onClose: (__VLS_ctx.closeNodeDetail) });
    var __VLS_105;
    var __VLS_106;
}
// @ts-ignore
[store, store, onGraphOpenTerminal, closeNodeDetail, closeNodeDetail, nodeArtifact, onAttachTerminal,];
var __VLS_99;
// @ts-ignore
[];
var __VLS_93;
if (__VLS_ctx.store.selectedRun) {
    const __VLS_110 = MergeDialog;
    // @ts-ignore
    const __VLS_111 = __VLS_asFunctionalComponent1(__VLS_110, new __VLS_110({
        ...{ 'onClose': {} },
        ...{ 'onMerged': {} },
        visible: (__VLS_ctx.showMergeDialog),
        kind: "run",
        itemId: (__VLS_ctx.store.selectedRun.id),
    }));
    const __VLS_112 = __VLS_111({
        ...{ 'onClose': {} },
        ...{ 'onMerged': {} },
        visible: (__VLS_ctx.showMergeDialog),
        kind: "run",
        itemId: (__VLS_ctx.store.selectedRun.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_111));
    let __VLS_115;
    const __VLS_116 = ({ close: {} },
        { onClose: (...[$event]) => {
                if (!(__VLS_ctx.store.selectedRun))
                    return;
                __VLS_ctx.showMergeDialog = false;
                // @ts-ignore
                [store, store, showMergeDialog, showMergeDialog,];
            } });
    const __VLS_117 = ({ merged: {} },
        { onMerged: (__VLS_ctx.onMerged) });
    var __VLS_113;
    var __VLS_114;
}
let __VLS_118;
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_119 = __VLS_asFunctionalComponent1(__VLS_118, new __VLS_118({
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.showTerminal),
    header: (__VLS_ctx.terminalLabel),
    draggable: (true),
    modal: (false),
    ...{ style: ({ width: '960px', height: '580px' }) },
    contentStyle: ({
        padding: 0,
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        overflow: 'hidden',
    }),
    ...{ class: "terminal-dialog" },
    position: "bottom",
}));
const __VLS_120 = __VLS_119({
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.showTerminal),
    header: (__VLS_ctx.terminalLabel),
    draggable: (true),
    modal: (false),
    ...{ style: ({ width: '960px', height: '580px' }) },
    contentStyle: ({
        padding: 0,
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        overflow: 'hidden',
    }),
    ...{ class: "terminal-dialog" },
    position: "bottom",
}, ...__VLS_functionalComponentArgsRest(__VLS_119));
let __VLS_123;
const __VLS_124 = ({ 'update:visible': {} },
    { 'onUpdate:visible': (...[$event]) => {
            !$event && __VLS_ctx.closeTerminal();
            // @ts-ignore
            [onMerged, showTerminal, terminalLabel, closeTerminal,];
        } });
/** @type {__VLS_StyleScopedClasses['terminal-dialog']} */ ;
const { default: __VLS_125 } = __VLS_121.slots;
if (__VLS_ctx.terminalSessionId) {
    const __VLS_126 = TerminalPanel;
    // @ts-ignore
    const __VLS_127 = __VLS_asFunctionalComponent1(__VLS_126, new __VLS_126({
        sessionId: (__VLS_ctx.terminalSessionId),
        nodeId: (__VLS_ctx.store.selectedNode?.id ?? ''),
        active: (__VLS_ctx.showTerminal),
        taskName: (__VLS_ctx.terminalLabel),
        readonly: (__VLS_ctx.terminalReadonly),
    }));
    const __VLS_128 = __VLS_127({
        sessionId: (__VLS_ctx.terminalSessionId),
        nodeId: (__VLS_ctx.store.selectedNode?.id ?? ''),
        active: (__VLS_ctx.showTerminal),
        taskName: (__VLS_ctx.terminalLabel),
        readonly: (__VLS_ctx.terminalReadonly),
    }, ...__VLS_functionalComponentArgsRest(__VLS_127));
}
// @ts-ignore
[store, showTerminal, terminalLabel, terminalSessionId, terminalSessionId, terminalReadonly,];
var __VLS_121;
var __VLS_122;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
