export interface AnalyticsInterface {
  identify: Function
  track: <K extends keyof TrackEventMap>(event: K, payload: TrackEventMap[K]) => void
}

export enum AnalyticsTrackKeysEnum {
  download = 'download',
  finish = 'finish',
  predict = 'predict',
  select_prompt_optimization = 'select_prompt_optimization',
  choose_provider = 'choose_provider',
  run_optimization = 'run_optimization',
  side_menu_select = 'side_menu_select',
  select_task = 'select_task',
  send_mail = 'send_mail',
}

interface TrackEventMap {
  [AnalyticsTrackKeysEnum.download]: { task: string }
  [AnalyticsTrackKeysEnum.finish]: { task: string }
  [AnalyticsTrackKeysEnum.predict]: { task: string }
  [AnalyticsTrackKeysEnum.select_prompt_optimization]: { option: string }
  [AnalyticsTrackKeysEnum.choose_provider]: { task: string }
  [AnalyticsTrackKeysEnum.run_optimization]: {
    task: string
    teacher_model: string
    student_model: string
    evaluation_metrics: string
  }
  [AnalyticsTrackKeysEnum.side_menu_select]: { option: string }
  [AnalyticsTrackKeysEnum.select_task]: { task: string }
  [AnalyticsTrackKeysEnum.send_mail]: { task: string; email: string }
}

class AnalyticsServiceClass {
  constructor() {
    this.init()
  }

  track<K extends keyof TrackEventMap>(key: K, payload: TrackEventMap[K]) {
    if (!import.meta.env.VITE_ANALYTICS_KEY) return
    window.analytics.track(key, payload)
  }

  identify(id: number, email: string) {
    if (!import.meta.env.VITE_ANALYTICS_KEY) return
    window.analytics.identify(id, { email })
  }

  private init() {
    if (!import.meta.env.VITE_ANALYTICS_KEY) return

    const script = document.createElement('script')
    script.type = 'text/javascript'
    script.innerHTML = `
      !function(){var i="analytics",analytics=window[i]=window[i]||[];if(!analytics.initialize)if(analytics.invoked)window.console&&console.error&&console.error("Segment snippet included twice.");else{analytics.invoked=!0;analytics.methods=["trackSubmit","trackClick","trackLink","trackForm","pageview","identify","reset","group","track","ready","alias","debug","page","screen","once","off","on","addSourceMiddleware","addIntegrationMiddleware","setAnonymousId","addDestinationMiddleware","register"];analytics.factory=function(e){return function(){if(window[i].initialized)return window[i][e].apply(window[i],arguments);var n=Array.prototype.slice.call(arguments);if(["track","screen","alias","group","page","identify"].indexOf(e)>-1){var c=document.querySelector("link[rel='canonical']");n.push({__t:"bpc",c:c&&c.getAttribute("href")||void 0,p:location.pathname,u:location.href,s:location.search,t:document.title,r:document.referrer})}n.unshift(e);analytics.push(n);return analytics}};for(var n=0;n<analytics.methods.length;n++){var key=analytics.methods[n];analytics[key]=analytics.factory(key)}analytics.load=function(key,n){var t=document.createElement("script");t.type="text/javascript";t.async=!0;t.setAttribute("data-global-segment-analytics-key",i);t.src="https://cdn.segment.com/analytics.js/v1/" + key + "/analytics.min.js";var r=document.getElementsByTagName("script")[0];r.parentNode.insertBefore(t,r);analytics._loadOptions=n};analytics._writeKey="${import.meta.env.VITE_ANALYTICS_KEY}";;analytics.SNIPPET_VERSION="5.2.0";
        analytics.load("${import.meta.env.VITE_ANALYTICS_KEY}");
        analytics.page();
      }}();
    `
    document.head.appendChild(script)
  }
}

export const AnalyticsService = new AnalyticsServiceClass()
