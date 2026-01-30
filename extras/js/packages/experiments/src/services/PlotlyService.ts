class PlotlyServiceClass {
  private plotly: typeof import('plotly.js-dist') | null = null

  async getPlotly() {
    if (typeof window === 'undefined') throw new Error('Plotly works only in browser')
    if (!this.plotly) {
      const module = await import('plotly.js-dist')
      this.plotly = module.default ?? module
    }
    return this.plotly
  }
}

export const plotlyService = new PlotlyServiceClass()
