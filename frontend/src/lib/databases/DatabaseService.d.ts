import type { DatabaseMetadata, LumlFile, Notebook } from './database.interfaces';
declare class DatabaseServiceClass {
    getDatabases(): Promise<IDBDatabaseInfo[]>;
    deleteDatabase(name: string): Promise<void>;
    createDatabase(id: string, metadata: DatabaseMetadata): Promise<any>;
    getDatabaseInfo(name: string): Promise<Notebook>;
    getDatabasesWithMetadata(): Promise<Notebook[]>;
    editDatabase(name: string, metadata: DatabaseMetadata): Promise<void>;
    createBackup(name: string): Promise<void>;
    getFileBlob(file: LumlFile): Promise<Blob>;
    private getVersion;
    private getLumlFiles;
}
export declare const DatabaseService: DatabaseServiceClass;
export {};
