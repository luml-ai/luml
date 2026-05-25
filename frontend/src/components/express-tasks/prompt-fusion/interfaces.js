import { CaseUpper, Hash, Braces, CircleArrowDown, CircleArrowUp, Cpu, BetweenHorizonalStart, } from 'lucide-vue-next';
export const PROMPT_FIELDS_ICONS = {
    string: CaseUpper,
    integer: Hash,
    float: Hash,
    complex: Braces,
};
export const PROMPT_NODES_ICONS = {
    input: CircleArrowDown,
    cpu: Cpu,
    gate: BetweenHorizonalStart,
    output: CircleArrowUp,
};
export var NodeTypeEnum;
(function (NodeTypeEnum) {
    NodeTypeEnum["input"] = "input";
    NodeTypeEnum["gate"] = "gate";
    NodeTypeEnum["processor"] = "processor";
    NodeTypeEnum["output"] = "output";
})(NodeTypeEnum || (NodeTypeEnum = {}));
export var PromptFieldTypeEnum;
(function (PromptFieldTypeEnum) {
    PromptFieldTypeEnum["string"] = "String";
    PromptFieldTypeEnum["integer"] = "Integer";
    PromptFieldTypeEnum["float"] = "Float";
    PromptFieldTypeEnum["complex"] = "Complex";
})(PromptFieldTypeEnum || (PromptFieldTypeEnum = {}));
