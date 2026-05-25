declare var __VLS_1: {}, __VLS_17: {};
type __VLS_Slots = {} & {
    form?: (props: typeof __VLS_1) => any;
} & {
    footer?: (props: typeof __VLS_17) => any;
};
declare const __VLS_base: any;
declare const __VLS_export: __VLS_WithSlots<typeof __VLS_base, __VLS_Slots>;
declare const _default: typeof __VLS_export;
export default _default;
type __VLS_WithSlots<T, S> = T & {
    new (): {
        $slots: S;
    };
};
