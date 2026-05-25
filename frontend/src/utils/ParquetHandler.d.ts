export interface PreviewResult {
    columns: string[];
    rows: Record<string, unknown>[];
}
export declare class ParquetHandler {
    private buffer;
    constructor(buffer: ArrayBuffer);
    init(): Promise<void>;
    read(): Promise<any>;
}
