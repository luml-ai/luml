export interface AnalyticsInterface {
    identify: Function;
    track: <K extends keyof TrackEventMap>(event: K, payload: TrackEventMap[K]) => void;
}
export declare enum AnalyticsTrackKeysEnum {
    download = "download",
    finish = "finish",
    predict = "predict",
    select_prompt_optimization = "select_prompt_optimization",
    choose_provider = "choose_provider",
    run_optimization = "run_optimization",
    side_menu_select = "side_menu_select",
    select_task = "select_task",
    send_mail = "send_mail"
}
interface TrackEventMap {
    [AnalyticsTrackKeysEnum.download]: {
        task: string;
    };
    [AnalyticsTrackKeysEnum.finish]: {
        task: string;
    };
    [AnalyticsTrackKeysEnum.predict]: {
        task: string;
    };
    [AnalyticsTrackKeysEnum.select_prompt_optimization]: {
        option: string;
    };
    [AnalyticsTrackKeysEnum.choose_provider]: {
        task: string;
    };
    [AnalyticsTrackKeysEnum.run_optimization]: {
        task: string;
        teacher_model: string;
        student_model: string;
        evaluation_metrics: string;
    };
    [AnalyticsTrackKeysEnum.side_menu_select]: {
        option: string;
    };
    [AnalyticsTrackKeysEnum.select_task]: {
        task: string;
    };
    [AnalyticsTrackKeysEnum.send_mail]: {
        task: string;
        email: string;
    };
}
declare class AnalyticsServiceClass {
    constructor();
    track<K extends keyof TrackEventMap>(key: K, payload: TrackEventMap[K]): void;
    identify(id: number, email: string): void;
    private init;
}
export declare const AnalyticsService: AnalyticsServiceClass;
export {};
