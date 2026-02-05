import type { PlotlyBarChartLayoutParams, PlotlyLineChartLayoutParams } from './interfaces'

export const plotlyLineChartLayout = (params: PlotlyLineChartLayoutParams) => {
  return {
    paper_bgcolor: params.bgColor,
    plot_bgcolor: params.bgColor,
    title: params.title,
    xaxis: {
      showline: true,
      showgrid: false,
      zeroline: false,
      linecolor: params.borderColor,
      linewidth: 2,
    },
    yaxis: {
      showline: false,
      gridcolor: params.gridColor,
      gridwidth: 2,
      zeroline: false,
      pad: 20,
      autorange: true,
      rangemode: 'normal',
      ticksuffix: ' ',
      automargin: true,
    },
    margin: { l: 0, r: 0, t: 2, b: 20 },
    showlegend: false,
    font: {
      family: 'Inter, sans-serif',
      size: 12,
      color: params.textColor,
    },
    hovermode: 'x unified',
  }
}

export const plotlyBarChartLayout = (params: PlotlyBarChartLayoutParams) => {
  return {
    paper_bgcolor: params.bgColor,
    plot_bgcolor: params.bgColor,
    title: params.title,
    barcornerradius: 6,
    xaxis: {
      showticklabels: false,
    },
    yaxis: {
      showline: false,
      gridcolor: params.gridColor,
      gridwidth: 2,
      autorange: true,
      rangemode: 'normal',
      ticksuffix: ' ',
      automargin: true,
    },
    margin: { l: 0, r: 0, t: 2, b: 0 },
    showlegend: false,
    font: {
      family: 'Inter, sans-serif',
      size: 12,
      color: params.textColor,
    },
  }
}
