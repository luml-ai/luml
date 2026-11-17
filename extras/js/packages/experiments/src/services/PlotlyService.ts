type Plotly = typeof import('plotly.js-basic-dist-min')

class PlotlyServiceClass {
  private loading: Promise<Plotly> | null = null

  getPlotly(): Promise<Plotly> {
    if (typeof window === 'undefined') {
      return Promise.reject(new Error('Plotly works only in browser'))
    }
    this.loading ??= import('plotly.js-basic-dist-min').then(
      (module) => module.default ?? module,
      (error: unknown) => {
        // A failed load is retried by the next caller.
        this.loading = null
        throw error
      },
    )
    return this.loading
  }

  /** Starts the download early; failures surface when a chart asks for Plotly. */
  preload(): void {
    this.getPlotly().catch(() => {})
  }
}

export const plotlyService = new PlotlyServiceClass()
