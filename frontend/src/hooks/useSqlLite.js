import initSqlJs from 'sql.js';
import { computed, ref } from 'vue';
export const useSqlLite = () => {
    const SQL = ref();
    const getSQL = computed(() => {
        if (!SQL.value)
            throw new Error('Init SQL before');
        return SQL.value;
    });
    async function initSql() {
        SQL.value = await initSqlJs({
            locateFile: () => `/sql-wasm.wasm`,
        });
    }
    return {
        initSql,
        getSQL,
    };
};
