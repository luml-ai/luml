import type { useUploadFlow } from '@/hooks/useUploadFlow';
export declare function useAgentWebSocket(uploadFlow?: ReturnType<typeof useUploadFlow>): {
    connected: any;
    reconnecting: any;
};
