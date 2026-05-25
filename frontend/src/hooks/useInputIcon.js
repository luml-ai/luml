import { X, PencilLine } from 'lucide-vue-next';
import { computed, onMounted, ref } from 'vue';
export const useInputIcon = (inputs, formRef, values, isShowEditIcon = true) => {
    const inputsStates = ref({});
    const inputsRefs = ref({});
    const getCurrentInputIcon = computed(() => (inputName) => {
        if (inputsStates.value[inputName])
            return X;
        else
            return isShowEditIcon ? PencilLine : null;
    });
    function setInputState(inputName, state) {
        setTimeout(() => {
            inputsStates.value[inputName] = state;
        }, 200);
    }
    function onIconClick(inputName) {
        if (getCurrentInputIcon.value(inputName) === X && formRef.value?.states[inputName]) {
            formRef.value.states[inputName] = { ...formRef.value.states[inputName], value: '' };
            values.value[inputName] ? (values.value[inputName] = '') : null;
        }
    }
    onMounted(() => {
        inputs.reduce((obj, input) => {
            if (!input.value)
                return obj;
            const el = input.value.$el;
            el.onblur = () => setInputState(el.name, false);
            el.onfocus = () => setInputState(el.name, true);
            obj[el.name] = el;
            inputsStates.value[el.name] = false;
            return obj;
        }, inputsRefs.value);
    });
    return { getCurrentInputIcon, onIconClick };
};
