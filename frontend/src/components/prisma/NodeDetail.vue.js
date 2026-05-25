/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { Tag, Button } from 'primevue';
import { Terminal, X, TrendingUp, ExternalLink } from 'lucide-vue-next';
import { usePrismaStore } from '@/stores/prisma';
import { displayStatus } from './board/board.types';
import { api } from '@/lib/api';
const props = defineProps();
const router = useRouter();
const store = usePrismaStore();
const node = computed(() => store.selectedNode);
const metric = computed(() => {
    if (node.value?.node_type !== 'run')
        return null;
    const val = node.value?.result?.artifacts?.metric;
    return val !== undefined && val !== null ? val : null;
});
const resolvedArtifact = computed(() => {
    if (props.artifact)
        return props.artifact;
    const link = node.value?.result?.artifact_link;
    if (link?.artifact_id) {
        return {
            artifactId: link.artifact_id,
            organizationId: link.organization_id,
            orbitId: link.orbit_id,
            collectionId: link.collection_id,
        };
    }
    return undefined;
});
function formatMetric(val) {
    if (typeof val === 'number') {
        return Number.isInteger(val) ? String(val) : val.toFixed(4);
    }
    return JSON.stringify(val);
}
function statusSeverity(status) {
    const map = {
        queued: 'secondary',
        running: 'info',
        waiting_input: 'warn',
        succeeded: 'success',
        failed: 'danger',
        canceled: 'secondary',
    };
    return map[status] ?? 'secondary';
}
const emit = defineEmits();
async function cancelNode() {
    if (!node.value)
        return;
    await api.dataAgent.sendNodeAction(node.value.id, 'cancel');
}
const isSessionLive = computed(() => {
    const n = node.value;
    if (!n?.session_id)
        return false;
    return n.is_alive || n.status === 'waiting_input';
});
function attachTerminal() {
    if (node.value?.session_id) {
        emit('attach-terminal', node.value.session_id, !isSessionLive.value);
    }
}
function openArtifact() {
    const ctx = resolvedArtifact.value;
    if (!ctx)
        return;
    const route = router.resolve({
        name: 'artifact',
        params: {
            organizationId: ctx.organizationId,
            id: ctx.orbitId,
            collectionId: ctx.collectionId,
            artifactId: ctx.artifactId,
        },
    });
    window.open(route.href, '_blank');
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
/** @type {__VLS_StyleScopedClasses['prop-row']} */ ;
/** @type {__VLS_StyleScopedClasses['prop-row']} */ ;
/** @type {__VLS_StyleScopedClasses['prop-row']} */ ;
/** @type {__VLS_StyleScopedClasses['artifact-link']} */ ;
if (__VLS_ctx.node) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "node-detail" },
    });
    /** @type {__VLS_StyleScopedClasses['node-detail']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
        ...{ class: "header" },
    });
    /** @type {__VLS_StyleScopedClasses['header']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "header-left" },
    });
    /** @type {__VLS_StyleScopedClasses['header-left']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
        ...{ class: "node-title" },
    });
    /** @type {__VLS_StyleScopedClasses['node-title']} */ ;
    (__VLS_ctx.node.node_type);
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.Tag} */
    Tag;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        value: (__VLS_ctx.displayStatus(__VLS_ctx.node.status)),
        severity: (__VLS_ctx.statusSeverity(__VLS_ctx.node.status)),
    }));
    const __VLS_2 = __VLS_1({
        value: (__VLS_ctx.displayStatus(__VLS_ctx.node.status)),
        severity: (__VLS_ctx.statusSeverity(__VLS_ctx.node.status)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_5;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
        ...{ 'onClick': {} },
        variant: "text",
        severity: "secondary",
    }));
    const __VLS_7 = __VLS_6({
        ...{ 'onClick': {} },
        variant: "text",
        severity: "secondary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_6));
    let __VLS_10;
    const __VLS_11 = ({ click: {} },
        { onClick: (...[$event]) => {
                if (!(__VLS_ctx.node))
                    return;
                __VLS_ctx.emit('close');
                // @ts-ignore
                [node, node, node, node, displayStatus, statusSeverity, emit,];
            } });
    const { default: __VLS_12 } = __VLS_8.slots;
    {
        const { icon: __VLS_13 } = __VLS_8.slots;
        let __VLS_14;
        /** @ts-ignore @type { | typeof __VLS_components.X} */
        X;
        // @ts-ignore
        const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
            size: (16),
        }));
        const __VLS_16 = __VLS_15({
            size: (16),
        }, ...__VLS_functionalComponentArgsRest(__VLS_15));
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
    var __VLS_8;
    var __VLS_9;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "body" },
    });
    /** @type {__VLS_StyleScopedClasses['body']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
        ...{ class: "section" },
    });
    /** @type {__VLS_StyleScopedClasses['section']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h4, __VLS_intrinsics.h4)({
        ...{ class: "section-title" },
    });
    /** @type {__VLS_StyleScopedClasses['section-title']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.dl, __VLS_intrinsics.dl)({
        ...{ class: "props" },
    });
    /** @type {__VLS_StyleScopedClasses['props']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "prop-row" },
    });
    /** @type {__VLS_StyleScopedClasses['prop-row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.dt, __VLS_intrinsics.dt)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.dd, __VLS_intrinsics.dd)({
        ...{ class: "mono" },
    });
    /** @type {__VLS_StyleScopedClasses['mono']} */ ;
    (__VLS_ctx.node.id);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "prop-row" },
    });
    /** @type {__VLS_StyleScopedClasses['prop-row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.dt, __VLS_intrinsics.dt)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.dd, __VLS_intrinsics.dd)({});
    (__VLS_ctx.node.depth);
    if (__VLS_ctx.node.branch) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "prop-row" },
        });
        /** @type {__VLS_StyleScopedClasses['prop-row']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.dt, __VLS_intrinsics.dt)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.dd, __VLS_intrinsics.dd)({
            ...{ class: "mono" },
        });
        /** @type {__VLS_StyleScopedClasses['mono']} */ ;
        (__VLS_ctx.node.branch);
    }
    if (__VLS_ctx.node.worktree_path) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "prop-row" },
        });
        /** @type {__VLS_StyleScopedClasses['prop-row']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.dt, __VLS_intrinsics.dt)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.dd, __VLS_intrinsics.dd)({
            ...{ class: "mono truncate" },
        });
        /** @type {__VLS_StyleScopedClasses['mono']} */ ;
        /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
        (__VLS_ctx.node.worktree_path);
    }
    if (__VLS_ctx.node.debug_retries > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "prop-row" },
        });
        /** @type {__VLS_StyleScopedClasses['prop-row']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.dt, __VLS_intrinsics.dt)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.dd, __VLS_intrinsics.dd)({});
        (__VLS_ctx.node.debug_retries);
    }
    if (__VLS_ctx.metric !== null) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
            ...{ class: "section" },
        });
        /** @type {__VLS_StyleScopedClasses['section']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "score-card" },
        });
        /** @type {__VLS_StyleScopedClasses['score-card']} */ ;
        let __VLS_19;
        /** @ts-ignore @type { | typeof __VLS_components.TrendingUp} */
        TrendingUp;
        // @ts-ignore
        const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
            size: (14),
            ...{ class: "score-icon" },
        }));
        const __VLS_21 = __VLS_20({
            size: (14),
            ...{ class: "score-icon" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_20));
        /** @type {__VLS_StyleScopedClasses['score-icon']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "score-label" },
        });
        /** @type {__VLS_StyleScopedClasses['score-label']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "score-value" },
        });
        /** @type {__VLS_StyleScopedClasses['score-value']} */ ;
        (__VLS_ctx.formatMetric(__VLS_ctx.metric));
    }
    if (__VLS_ctx.resolvedArtifact) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
            ...{ class: "section" },
        });
        /** @type {__VLS_StyleScopedClasses['section']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.h4, __VLS_intrinsics.h4)({
            ...{ class: "section-title" },
        });
        /** @type {__VLS_StyleScopedClasses['section-title']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (__VLS_ctx.openArtifact) },
            ...{ class: "artifact-link" },
        });
        /** @type {__VLS_StyleScopedClasses['artifact-link']} */ ;
        let __VLS_24;
        /** @ts-ignore @type { | typeof __VLS_components.ExternalLink} */
        ExternalLink;
        // @ts-ignore
        const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({
            size: (13),
        }));
        const __VLS_26 = __VLS_25({
            size: (13),
        }, ...__VLS_functionalComponentArgsRest(__VLS_25));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    }
    if (Object.keys(__VLS_ctx.node.payload).length > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
            ...{ class: "section" },
        });
        /** @type {__VLS_StyleScopedClasses['section']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.h4, __VLS_intrinsics.h4)({
            ...{ class: "section-title" },
        });
        /** @type {__VLS_StyleScopedClasses['section-title']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.pre, __VLS_intrinsics.pre)({
            ...{ class: "json-preview" },
        });
        /** @type {__VLS_StyleScopedClasses['json-preview']} */ ;
        (JSON.stringify(__VLS_ctx.node.payload, null, 2));
    }
    if (Object.keys(__VLS_ctx.node.result).length > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
            ...{ class: "section" },
        });
        /** @type {__VLS_StyleScopedClasses['section']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.h4, __VLS_intrinsics.h4)({
            ...{ class: "section-title" },
        });
        /** @type {__VLS_StyleScopedClasses['section-title']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.pre, __VLS_intrinsics.pre)({
            ...{ class: "json-preview" },
        });
        /** @type {__VLS_StyleScopedClasses['json-preview']} */ ;
        (JSON.stringify(__VLS_ctx.node.result, null, 2));
    }
    if (__VLS_ctx.node.session_id || __VLS_ctx.node.status === 'running' || __VLS_ctx.node.status === 'waiting_input') {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "actions" },
        });
        /** @type {__VLS_StyleScopedClasses['actions']} */ ;
        if (__VLS_ctx.node.session_id) {
            let __VLS_29;
            /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
            Button;
            // @ts-ignore
            const __VLS_30 = __VLS_asFunctionalComponent1(__VLS_29, new __VLS_29({
                ...{ 'onClick': {} },
                severity: (__VLS_ctx.isSessionLive ? 'info' : 'secondary'),
            }));
            const __VLS_31 = __VLS_30({
                ...{ 'onClick': {} },
                severity: (__VLS_ctx.isSessionLive ? 'info' : 'secondary'),
            }, ...__VLS_functionalComponentArgsRest(__VLS_30));
            let __VLS_34;
            const __VLS_35 = ({ click: {} },
                { onClick: (__VLS_ctx.attachTerminal) });
            const { default: __VLS_36 } = __VLS_32.slots;
            let __VLS_37;
            /** @ts-ignore @type { | typeof __VLS_components.Terminal} */
            Terminal;
            // @ts-ignore
            const __VLS_38 = __VLS_asFunctionalComponent1(__VLS_37, new __VLS_37({
                size: (14),
            }));
            const __VLS_39 = __VLS_38({
                size: (14),
            }, ...__VLS_functionalComponentArgsRest(__VLS_38));
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
            (__VLS_ctx.isSessionLive ? 'Terminal' : 'View Log');
            // @ts-ignore
            [node, node, node, node, node, node, node, node, node, node, node, node, node, node, node, node, metric, metric, formatMetric, resolvedArtifact, openArtifact, isSessionLive, isSessionLive, attachTerminal,];
            var __VLS_32;
            var __VLS_33;
        }
        if (__VLS_ctx.node.status === 'running' || __VLS_ctx.node.status === 'waiting_input') {
            let __VLS_42;
            /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
            Button;
            // @ts-ignore
            const __VLS_43 = __VLS_asFunctionalComponent1(__VLS_42, new __VLS_42({
                ...{ 'onClick': {} },
                severity: "warn",
                variant: "outlined",
            }));
            const __VLS_44 = __VLS_43({
                ...{ 'onClick': {} },
                severity: "warn",
                variant: "outlined",
            }, ...__VLS_functionalComponentArgsRest(__VLS_43));
            let __VLS_47;
            const __VLS_48 = ({ click: {} },
                { onClick: (__VLS_ctx.cancelNode) });
            const { default: __VLS_49 } = __VLS_45.slots;
            let __VLS_50;
            /** @ts-ignore @type { | typeof __VLS_components.X} */
            X;
            // @ts-ignore
            const __VLS_51 = __VLS_asFunctionalComponent1(__VLS_50, new __VLS_50({
                size: (14),
            }));
            const __VLS_52 = __VLS_51({
                size: (14),
            }, ...__VLS_functionalComponentArgsRest(__VLS_51));
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
            // @ts-ignore
            [node, node, cancelNode,];
            var __VLS_45;
            var __VLS_46;
        }
    }
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
