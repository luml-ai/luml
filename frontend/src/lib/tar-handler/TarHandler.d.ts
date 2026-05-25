export declare class TarHandler {
    private buffer;
    private view;
    private fileIndex;
    constructor(buffer: ArrayBuffer);
    private align512;
    private readAscii;
    private readOctal;
    private readFile;
    scan(): Map<string, [number, number]>;
    getManifest(): any;
}
