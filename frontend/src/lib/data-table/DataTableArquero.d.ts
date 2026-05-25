import { type FilterItem, type IDataTable } from './interfaces';
import { Observable } from '@/utils/observable/Observable';
export type SelectTableEvent = {
    name: string;
    size: number;
} | null;
export type Events = {
    SELECT_TABLE: SelectTableEvent;
};
export declare class DataTableArquero extends Observable<Events> implements IDataTable {
    private dataTable;
    private selectedColumns;
    private filters;
    constructor();
    private getCurrentData;
    private filteredRow;
    createFormCSV(file: File): Promise<void>;
    downloadCSV(fileName?: string): Promise<void>;
    getColumnsCount(): number;
    getRowsCount(): number;
    clearTable(): void;
    getColumnNames(): any;
    getObjects(): any;
    setSelectedColumns(columns: string[]): void;
    getSelectedColumns(): string[];
    setFilters(filters: FilterItem[]): void;
    getFilters(): FilterItem[];
    getDataForTraining(): any;
    resetData(): void;
}
