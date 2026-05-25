import { type TarAttachmentsProviderConfig } from '@luml/attachments';
export declare function useTarAttachmentsProvider(): {
    provider: any;
    loading: any;
    error: any;
    init: (config: TarAttachmentsProviderConfig) => Promise<void>;
};
