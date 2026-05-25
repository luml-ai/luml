export type ObservableStructure = {
    [p: string]: unknown;
};
export type ObserverStopHandle = () => boolean;
export interface Observable<Events extends ObservableStructure> {
    on<K extends keyof Events>(event: K, callback: (a: Events[K]) => void): ObserverStopHandle;
    once<K extends keyof Events>(event: K, callback: (a: Events[K]) => void): ObserverStopHandle;
    off<K extends keyof Events>(event: K, callback: (a: Events[K]) => void): boolean;
}
type Listeners<Events extends ObservableStructure> = {
    [s in keyof Events]: Set<(a: Events[s]) => void>;
};
/**
 * Abstract Class Observable implements events management for child instance.
 * @abstract Observable
 */
export declare abstract class Observable<Events extends ObservableStructure> {
    protected _listeners: Listeners<Events>;
    protected emit<K extends keyof Events>(event: K, value?: Events[K]): boolean;
}
export {};
