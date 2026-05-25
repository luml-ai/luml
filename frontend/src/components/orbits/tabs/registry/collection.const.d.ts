import type { DialogPassThroughOptions, MultiSelectPassThroughOptions } from 'primevue';
import { OrbitCollectionTypeEnum } from '@/lib/api/orbit-collections/interfaces';
export declare const COLLECTION_CREATOR_DIALOG_PT: DialogPassThroughOptions;
export declare const COLLECTION_TYPE_SELECT_PT: MultiSelectPassThroughOptions;
export declare const COLLECTION_TYPE_OPTIONS: {
    label: string;
    value: OrbitCollectionTypeEnum;
    disabled: boolean;
}[];
export declare const COLLECTION_TYPE_CONFIG: {
    model: {
        label: string;
        icon: any;
    };
    dataset: {
        label: string;
        icon: any;
    };
    experiment: {
        label: string;
        icon: any;
    };
    mixed: {
        label: string;
        icon: any;
    };
};
