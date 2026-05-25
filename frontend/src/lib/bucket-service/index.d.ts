import type { FileIndex } from '../api/artifacts/interfaces';
export declare class ModelDownloader {
    url: string;
    constructor(url: string);
    getFileFromBucket<T = any>(fileIndex: FileIndex, fileName: string, buffer?: boolean, outerOffset?: number, signal?: AbortSignal): Promise<T>;
    getRangeHeader(fileIndex: FileIndex, fileName: string, outerOffset?: number): string;
}
