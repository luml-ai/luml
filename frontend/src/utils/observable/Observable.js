/**
 * Abstract Class Observable implements events management for child instance.
 * @abstract Observable
 */
export class Observable {
    _listeners = {};
    on(event, callback) {
        if (!(this._listeners[event] instanceof Set)) {
            this._listeners[event] = new Set();
        }
        if (this._listeners[event].has(callback)) {
            return () => false;
        }
        this._listeners[event].add(callback);
        return () => this.off(event, callback);
    }
    once(event, callback) {
        const wrappedCallback = (a) => {
            callback(a);
            this.off(event, wrappedCallback);
        };
        return this.on(event, wrappedCallback);
    }
    off(event, callback) {
        return !!this._listeners[event]?.delete(callback);
    }
    emit(event, value) {
        // if (process.env.APP_DEBUG_OBSERVER_EVENTS) {
        //   console.warn(`Observer -> emit event -> ${event as string}`)
        // }
        if (!(this._listeners[event] instanceof Set)) {
            return false;
        }
        const self = this;
        setTimeout(() => {
            self._listeners[event].forEach((callback) => {
                callback(value);
            });
        });
        return true;
    }
}
