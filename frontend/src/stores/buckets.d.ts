export declare enum BucketValidationErrorCode {
    INVALID_STATUS = "INVALID_STATUS",
    RANGE_NOT_SUPPORTED = "RANGE_NOT_SUPPORTED",
    UNKNOWN = "UNKNOWN"
}
export declare class BucketValidationError extends Error {
    code: BucketValidationErrorCode;
    constructor(code: BucketValidationErrorCode);
    getMessage(): string;
}
export declare const useBucketsStore: any;
