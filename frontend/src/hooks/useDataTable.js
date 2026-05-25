import { DataTableArquero } from '@/lib/data-table/DataTableArquero';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useToast } from 'primevue';
import { incorrectGroupWarning, incorrectTargetWarning } from '@/lib/primevue/data/toasts';
const initialState = {
    startedTableData: null,
    columnsCount: undefined,
    rowsCount: undefined,
    target: '',
    group: [],
    selectedColumns: [],
    filters: [],
    viewValues: null,
    columnTypes: {},
    inputsOutputsColumns: [],
};
export const useDataTable = (validator) => {
    const toast = useToast();
    const dataTable = new DataTableArquero();
    const startedTableData = ref(initialState.startedTableData);
    const columnsCount = ref(initialState.columnsCount);
    const rowsCount = ref(initialState.rowsCount);
    const target = ref(initialState.target);
    const group = ref(initialState.group);
    const selectedColumns = ref(initialState.selectedColumns);
    const filters = ref(initialState.filters);
    const viewValues = ref(initialState.viewValues);
    const columnTypes = ref(initialState.columnTypes);
    const inputsOutputsColumns = ref(initialState.inputsOutputsColumns);
    const isTableExist = computed(() => !!startedTableData.value);
    const fileData = computed(() => ({
        name: startedTableData.value?.fileName,
        size: startedTableData.value?.fileSize,
    }));
    const uploadDataErrors = computed(() => validator(startedTableData.value?.fileSize, startedTableData.value?.columnsCount, startedTableData.value?.rowsCount));
    const isUploadWithErrors = computed(() => {
        const errors = uploadDataErrors.value;
        for (const key in errors) {
            if (errors[key])
                return true;
        }
        return false;
    });
    const getAllColumnNames = computed(() => startedTableData.value?.columnNames || []);
    const getTarget = computed(() => target.value);
    const getGroup = computed(() => group.value);
    const getFilters = computed(() => filters.value);
    const getInputsColumns = computed(() => inputsOutputsColumns.value
        .filter((column) => {
        const isColumnAvailable = selectedColumns.value.length
            ? selectedColumns.value.includes(column.name)
            : true;
        return isColumnAvailable && column.variant === 'input';
    })
        .map((column) => column.name));
    const getOutputsColumns = computed(() => inputsOutputsColumns.value
        .filter((column) => {
        const isColumnAvailable = selectedColumns.value.length
            ? selectedColumns.value.includes(column.name)
            : true;
        return isColumnAvailable && column.variant === 'output';
    })
        .map((column) => column.name));
    async function onSelectFile(file) {
        await dataTable.createFormCSV(file);
    }
    function onRemoveFile() {
        dataTable.clearTable();
        resetState();
    }
    function setColumnTypes(row) {
        for (const key in row) {
            if (Number(row[key]))
                columnTypes.value[key] = 'number';
            else
                columnTypes.value[key] = 'string';
        }
    }
    function onSelectTable(event) {
        resetState();
        if (event) {
            const columnsCount = dataTable.getColumnsCount();
            const rowsCount = dataTable.getRowsCount();
            const columnNames = dataTable.getColumnNames();
            const values = dataTable.getObjects();
            viewValues.value = dataTable.getObjects();
            target.value = columnNames[columnNames.length - 1];
            setColumnTypes(values[0]);
            inputsOutputsColumns.value = columnNames.map((column, index, self) => {
                if (index === self.length - 1) {
                    return { name: column, variant: 'output' };
                }
                else {
                    return { name: column, variant: 'input' };
                }
            });
            startedTableData.value = {
                fileSize: event.size,
                fileName: event.name,
                columnsCount,
                rowsCount,
                columnNames,
                values,
            };
        }
    }
    function setTarget(column) {
        if (getGroup.value.includes(column)) {
            toast.add(incorrectTargetWarning);
            return;
        }
        target.value = column;
    }
    function changeGroup(column) {
        if (target.value === column) {
            toast.add(incorrectGroupWarning);
            return;
        }
        const columnExist = group.value.includes(column);
        if (columnExist) {
            group.value = group.value.filter((item) => item !== column);
        }
        else {
            group.value.push(column);
        }
    }
    function downloadCSV() {
        dataTable.downloadCSV(`dfs-${startedTableData.value?.fileName}`);
    }
    function setSelectedColumns(columns) {
        dataTable.setSelectedColumns(columns);
        selectedColumns.value = dataTable.getSelectedColumns();
        viewValues.value = dataTable.getObjects();
        columnsCount.value = dataTable.getColumnsCount();
    }
    function setFilters(newFilters) {
        dataTable.setFilters(newFilters);
        filters.value = newFilters;
        viewValues.value = dataTable.getObjects();
    }
    function getDataForTraining() {
        return dataTable.getDataForTraining();
    }
    function resetState() {
        startedTableData.value = initialState.startedTableData;
        columnsCount.value = initialState.columnsCount;
        rowsCount.value = initialState.rowsCount;
        target.value = initialState.target;
        group.value = initialState.group;
        selectedColumns.value = initialState.selectedColumns;
        filters.value = initialState.filters;
        viewValues.value = initialState.viewValues;
        columnTypes.value = initialState.columnTypes;
    }
    watch(startedTableData, (value) => {
        columnsCount.value = value?.columnsCount;
        rowsCount.value = value?.rowsCount;
    });
    onMounted(() => {
        dataTable.on('SELECT_TABLE', onSelectTable);
    });
    onBeforeUnmount(() => {
        dataTable.off('SELECT_TABLE', onSelectTable);
        onRemoveFile();
    });
    return {
        isTableExist,
        fileData,
        uploadDataErrors,
        isUploadWithErrors,
        columnsCount,
        rowsCount,
        getAllColumnNames,
        viewValues,
        getTarget,
        getGroup,
        selectedColumns,
        getFilters,
        columnTypes,
        inputsOutputsColumns,
        getInputsColumns,
        getOutputsColumns,
        onSelectFile,
        onRemoveFile,
        setTarget,
        changeGroup,
        setSelectedColumns,
        downloadCSV,
        setFilters,
        getDataForTraining,
    };
};
