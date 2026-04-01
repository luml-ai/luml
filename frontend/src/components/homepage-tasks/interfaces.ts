export interface TaskData {
  id: number
  icon: string
  title: string
  description: string
  btnText?: string
  linkName?: string
  tooltipData: string
  isAvailable: boolean
  isDisabled?: boolean
  analyticsTaskName: string
  dropdownOptions?: TaskDropdownOption[]
}

export interface TaskDropdownOption {
  label: string
  route?: string
}

export interface TaskList {
  label: string
  tasks: TaskData[]
}
