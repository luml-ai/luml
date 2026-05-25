import type { FilterItem } from '@/lib/data-table/interfaces';
export type ColumnType = 'number' | 'string' | 'date';
export type PromptFusionColumn = {
    name: string;
    variant: 'input' | 'output';
};
export type ValidatorFunction = (size?: number, columns?: number, rows?: number) => {
    size: boolean;
    columns: boolean;
    rows: boolean;
};
export declare const useDataTable: (validator: ValidatorFunction) => {
    isTableExist: any;
    fileData: any;
    uploadDataErrors: any;
    isUploadWithErrors: any;
    columnsCount: any;
    rowsCount: any;
    getAllColumnNames: any;
    viewValues: any;
    getTarget: any;
    getGroup: any;
    selectedColumns: any;
    getFilters: any;
    columnTypes: any;
    inputsOutputsColumns: any;
    getInputsColumns: any;
    getOutputsColumns: any;
    onSelectFile: (file: File) => Promise<void>;
    onRemoveFile: () => void;
    setTarget: (column: string) => void;
    changeGroup: (column: string) => void;
    setSelectedColumns: (columns: string[]) => void;
    downloadCSV: () => void;
    setFilters: (newFilters: FilterItem[]) => void;
    getDataForTraining: () => any;
};
