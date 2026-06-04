export function getStageBadgeStyle(stageName: string): Record<string, string> {
  const lower = stageName.toLowerCase()
  if (lower === 'production') {
    return {
      backgroundColor: '#DCFCE7',
      color: '#15803D',
      borderColor: 'transparent',
    }
  }
  if (lower === 'staging' || lower === 'pre-production') {
    return {
      backgroundColor: '#FFEDD5',
      color: '#C2410C',
      borderColor: 'transparent',
    }
  }
  return {
    backgroundColor: '#DBEAFE',
    color: '#1D4ED8',
    borderColor: 'transparent',
  }
}
