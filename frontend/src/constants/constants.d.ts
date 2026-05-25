import type { TaskData } from '@/components/homepage-tasks/interfaces';
export declare const SIDEBAR_SECTIONS: {
    id: string;
    label: string;
    items: {
        id: number;
        label: string;
        icon: any;
        route: string;
        disabled: boolean;
        tooltipMessage: null;
        analyticsOption: string;
        authRequired: boolean;
    }[];
}[];
export declare const SIDEBAR_MENU_BOTTOM: {
    id: number;
    label: string;
    icon: any;
    link: string;
}[];
type IAppTaskData = TaskData & {
    isAvailable: boolean;
};
export declare const availableTasks: IAppTaskData[];
export declare const classificationResources: {
    label: string;
    link: string;
}[];
export declare const regressionResources: {
    label: string;
    link: string;
}[];
export declare const promptFusionResources: {
    label: string;
    link: string;
}[];
export declare const tabularSteps: {
    id: number;
    text: string;
}[];
export {};
