import type { ColumnPassThroughOptions, DataTablePassThroughOptions } from 'primevue';
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces';
export declare const TABLE_PT: DataTablePassThroughOptions;
export declare const STATUS_TAGS_CONFIG: {
    deletion_failed: {
        severity: string;
        text: string;
    };
    pending_deletion: {
        severity: string;
        text: string;
    };
    pending_upload: {
        severity: string;
        text: string;
    };
    upload_failed: {
        severity: string;
        text: string;
    };
    uploaded: {
        severity: string;
        text: string;
    };
};
export declare const TYPE_COLUMN_PT: ColumnPassThroughOptions;
export declare const columnBodyStyle = "white-space: nowrap; overflow:hidden; text-overflow: ellipsis;";
export declare const ARTIFACT_TYPE_TAGS_CONFIG: {
    model: {
        severity: string;
        text: string;
        icon: any;
    };
    experiment: {
        severity: string;
        text: string;
        icon: any;
    };
    dataset: {
        severity: string;
        text: string;
        icon: any;
    };
};
export declare const ARTIFACT_TYPE_OPTIONS: {
    label: string;
    value: ArtifactTypeEnum;
    icon: any;
    color: string;
}[];
