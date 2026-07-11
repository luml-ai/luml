export type ObservableStructure = {
  [p: string]: unknown
}

export type ObserverStopHandle = () => boolean

type Listeners<Events extends ObservableStructure> = {
  [s in keyof Events]: Set<(a: Events[s]) => void>
}

/**
 * Abstract Class Observable implements events management for child instance.
 * @abstract Observable
 */
export abstract class Observable<Events extends ObservableStructure> {
  protected _listeners = {} as Listeners<Events>

  on<K extends keyof Events>(event: K, callback: (a: Events[K]) => void): () => boolean {
    if (!(this._listeners[event] instanceof Set)) {
      this._listeners[event] = new Set()
    }

    if (this._listeners[event].has(callback)) {
      return () => false
    }

    this._listeners[event].add(callback)

    return () => this.off(event, callback)
  }

  once<K extends keyof Events>(event: K, callback: (a: Events[K]) => void) {
    const wrappedCallback = (a: Events[K]) => {
      callback(a)
      this.off(event, wrappedCallback)
    }

    return this.on(event, wrappedCallback)
  }

  off<K extends keyof Events>(event: K, callback: (a: Events[K]) => void): boolean {
    return !!this._listeners[event]?.delete(callback)
  }

  protected emit<K extends keyof Events>(event: K, value?: Events[K]): boolean {
    // if (process.env.APP_DEBUG_OBSERVER_EVENTS) {
    //   console.warn(`Observer -> emit event -> ${event as string}`)
    // }

    if (!(this._listeners[event] instanceof Set)) {
      return false
    }

    setTimeout(() => {
      this._listeners[event].forEach((callback) => {
        callback(value as Events[typeof event])
      })
    })

    return true
  }
}
