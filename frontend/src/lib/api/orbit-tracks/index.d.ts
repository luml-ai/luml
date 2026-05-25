import type { AxiosInstance } from 'axios';
import type { ITrack, ITracksList, ITrackCreate, ITrackUpdate, ITrackArtifact, ITrackArtifactCreate, ITrackArtifactUpdate, ITrackArtifactUpdateResponse, ITrackEntriesList, ITrackStage, ITrackStageCreate, ITrackStageUpdate, ITrackStagesList, GetTrackEntriesListParams } from './interfaces';
export declare class OrbitTracksApi {
    private api;
    constructor(api: AxiosInstance);
    createTrack(organizationId: string, orbitId: string, data: ITrackCreate): Promise<ITrack>;
    listTracks(organizationId: string, orbitId: string): Promise<ITracksList>;
    getTrack(organizationId: string, orbitId: string, trackId: string): Promise<ITrack>;
    updateTrack(organizationId: string, orbitId: string, trackId: string, data: ITrackUpdate): Promise<ITrack>;
    deleteTrack(organizationId: string, orbitId: string, trackId: string): Promise<void>;
    addEntry(organizationId: string, orbitId: string, trackId: string, data: ITrackArtifactCreate): Promise<ITrackArtifact>;
    listEntries(organizationId: string, orbitId: string, trackId: string, params?: GetTrackEntriesListParams): Promise<ITrackEntriesList>;
    patchEntry(organizationId: string, orbitId: string, trackId: string, entryId: string, data: ITrackArtifactUpdate, force?: boolean): Promise<ITrackArtifactUpdateResponse>;
    deleteEntry(organizationId: string, orbitId: string, trackId: string, entryId: string): Promise<void>;
    listArtifactEntries(organizationId: string, orbitId: string, artifactId: string): Promise<ITrackEntriesList>;
    createStage(organizationId: string, orbitId: string, trackId: string, data: ITrackStageCreate): Promise<ITrackStage>;
    listStages(organizationId: string, orbitId: string, trackId: string): Promise<ITrackStagesList>;
    updateStage(organizationId: string, orbitId: string, trackId: string, stageId: string, data: ITrackStageUpdate): Promise<ITrackStage>;
    deleteStage(organizationId: string, orbitId: string, trackId: string, stageId: string, force?: boolean): Promise<void>;
}
