// export const ROUTES = {
//   HOME: '/',
//   GROUP: (groupId: string) => `/groups/${groupId}`,
// } as const

// export const ROUTE_NAMES = {

// }

export const ROUTE_NAMES = {
  HOME: 'home',
  EXPERIMENT: 'experiment',
}

export const ROUTES = {
  [ROUTE_NAMES.HOME]: '/',
  [ROUTE_NAMES.EXPERIMENT]: 'experiments/:experimentId',
}
