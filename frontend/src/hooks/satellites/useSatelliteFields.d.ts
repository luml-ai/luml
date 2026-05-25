import type { Satellite } from '@/lib/api/satellites/interfaces';
import type { ModelArtifact } from '@/lib/api/artifacts/interfaces';
export declare const useSatelliteFields: () => {
    fields: any;
    setFields: (satellite: Satellite | null, model: ModelArtifact | null, currentValues: Record<string, any>) => void;
};
