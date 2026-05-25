import { fromCSV, escape } from 'arquero';
import { FilterType } from './interfaces';
import { Observable } from '@/utils/observable/Observable';
export class DataTableArquero extends Observable {
    dataTable = null;
    selectedColumns = [];
    filters = [];
    constructor() {
        super();
    }
    getCurrentData() {
        if (!this.dataTable)
            throw new Error('You need createTable before');
        let data = this.dataTable;
        if (this.filters.length)
            data = data.filter(escape((row) => this.filteredRow(row, this.filters)));
        if (this.selectedColumns.length)
            data = data.select(this.selectedColumns);
        return data;
    }
    filteredRow(row, filters) {
        return filters.every((filter) => {
            const columnValue = row[filter.column];
            const parameter = isNaN(filter.parameter) ? filter.parameter : +filter.parameter;
            switch (filter.filterType) {
                case FilterType.Equals:
                    return columnValue === parameter;
                case FilterType.NotEquals:
                    return columnValue !== parameter;
                case FilterType.LessThan:
                    return columnValue < parameter;
                case FilterType.LessThanOrEqualTo:
                    return columnValue <= parameter;
                case FilterType.GreaterThan:
                    return columnValue > parameter;
                case FilterType.GreaterThanOrEqualTo:
                    return columnValue >= parameter;
                default:
                    return true;
            }
        });
    }
    async createFormCSV(file) {
        this.resetData();
        this.dataTable = fromCSV(await file.text());
        this.emit('SELECT_TABLE', { name: file.name, size: file.size });
    }
    async downloadCSV(fileName = 'output.csv') {
        const csvContent = this.getCurrentData().toCSV();
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
    getColumnsCount() {
        return this.getCurrentData().numCols();
    }
    getRowsCount() {
        return this.getCurrentData().numRows();
    }
    clearTable() {
        this.resetData();
        this.emit('SELECT_TABLE', null);
    }
    getColumnNames() {
        return this.getCurrentData().columnNames();
    }
    getObjects() {
        return this.getCurrentData().objects();
    }
    setSelectedColumns(columns) {
        this.selectedColumns = columns;
    }
    getSelectedColumns() {
        return this.selectedColumns;
    }
    setFilters(filters) {
        this.filters = filters;
    }
    getFilters() {
        return this.filters;
    }
    getDataForTraining() {
        const data = this.getObjects().reduce((acc, object) => {
            for (const key in object) {
                const value = object[key];
                if (acc[key]) {
                    acc[key].push(value);
                }
                else {
                    acc[key] = [value];
                }
            }
            return acc;
        }, {});
        return data;
    }
    resetData() {
        this.dataTable = null;
        this.selectedColumns = [];
        this.filters = [];
    }
}
