/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, onMounted, onUnmounted, watch } from 'vue';
import { useToast } from 'primevue/usetoast';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import { api } from '@/lib/api';
import '@xterm/xterm/css/xterm.css';
const props = defineProps();
const toast = useToast();
const emit = defineEmits();
const ANSI_RE = /\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*\x07|\][^\x1b]*\x1b\\|[()][AB012]|[@-Z\\-_])/g;
function hasPrintableContent(data) {
    const stripped = new TextDecoder().decode(data).replace(ANSI_RE, '');
    for (let i = 0; i < stripped.length; i++) {
        const c = stripped.charCodeAt(i);
        if (c > 0x1f && c !== 0x7f)
            return true;
    }
    return false;
}
const termRef = ref();
const isIdle = ref(false);
let terminal = null;
let fitAddon = null;
let ws = null;
let resizeObserver = null;
function onWaitingForInput() {
    if (isIdle.value)
        return;
    isIdle.value = true;
    emit('idle-change', true);
    toast.add({
        severity: 'warn',
        summary: 'Waiting for input',
        detail: props.taskName ?? 'Unknown task',
        life: 5000,
    });
}
function onOutputReceived() {
    if (!isIdle.value)
        return;
    isIdle.value = false;
    emit('idle-change', false);
}
let scrollbackDone = false;
async function loadReadonly() {
    if (!terminal)
        return;
    try {
        const buf = await api.dataAgent.getSessionScrollback(props.nodeId, props.sessionId);
        terminal.write(new Uint8Array(buf));
        terminal.write('\r\n\x1b[33m[Session ended]\x1b[0m\r\n');
    }
    catch {
        terminal.write('\x1b[31m[No scrollback available]\x1b[0m\r\n');
    }
}
function connect() {
    if (!terminal)
        return;
    ws = api.dataAgent.createTerminalWebSocket(props.sessionId);
    ws.binaryType = 'arraybuffer';
    scrollbackDone = false;
    terminal.write('\x1b[?25l');
    ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
            const bytes = new Uint8Array(event.data);
            terminal.write(bytes);
            if (!scrollbackDone) {
                scrollbackDone = true;
                setTimeout(() => {
                    fitAddon?.fit();
                    sendResize();
                    terminal?.scrollToBottom();
                }, 50);
            }
            if (hasPrintableContent(bytes)) {
                onOutputReceived();
            }
        }
        else {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'exit') {
                    terminal.write(`\r\n\x1b[33m[Process exited with code ${msg.code}]\x1b[0m\r\n`);
                }
                else if (msg.type === 'waiting_for_input') {
                    onWaitingForInput();
                }
            }
            catch {
                // ignore
            }
        }
    };
    ws.onclose = () => {
        terminal?.write('\r\n\x1b[31m[Disconnected]\x1b[0m\r\n');
    };
    terminal.onData((data) => {
        if (ws?.readyState === WebSocket.OPEN) {
            ws.send(new TextEncoder().encode(data));
        }
    });
}
function sendResize() {
    if (ws?.readyState === WebSocket.OPEN && terminal) {
        ws.send(JSON.stringify({
            type: 'resize',
            cols: terminal.cols,
            rows: terminal.rows,
        }));
    }
}
onMounted(() => {
    terminal = new Terminal({
        cursorBlink: !props.readonly,
        disableStdin: props.readonly,
        fontSize: 14,
        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
        theme: {
            background: '#020617',
            foreground: '#e2e8f0',
            cursor: '#60a5fa',
            selectionBackground: '#334155',
        },
    });
    fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);
    terminal.loadAddon(new WebLinksAddon());
    if (termRef.value) {
        terminal.open(termRef.value);
        resizeObserver = new ResizeObserver(() => {
            fitAddon?.fit();
            sendResize();
        });
        resizeObserver.observe(termRef.value);
        setTimeout(() => {
            fitAddon?.fit();
            if (props.readonly) {
                loadReadonly();
            }
            else {
                sendResize();
                connect();
            }
        }, 200);
    }
});
watch(() => props.active, (isActive) => {
    if (isActive) {
        setTimeout(() => {
            fitAddon?.fit();
            sendResize();
        }, 50);
    }
});
onUnmounted(() => {
    resizeObserver?.disconnect();
    ws?.close();
    terminal?.dispose();
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
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ref: "termRef",
    ...{ class: "terminal-container" },
});
/** @type {__VLS_StyleScopedClasses['terminal-container']} */ ;
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
