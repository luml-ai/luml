import type { TaskData } from '@/components/homepage-tasks/interfaces'
import {
  CirclePlay,
  Zap,
  File,
  Orbit,
  Notebook,
  BotMessageSquare,
  MessageCircleCode,
} from 'lucide-vue-next'
import TabularClassificationIcon from '@/assets/img/cards-icons/tabular-classification.svg'
import TabularRegressionIcon from '@/assets/img/cards-icons/tabular-regression.svg'
import ForecastingIcon from '@/assets/img/cards-icons/forecasting.svg'
import ConversationalQAIcon from '@/assets/img/cards-icons/conversational-qa.svg'

export const SIDEBAR_MENU = [
  {
    id: 1,
    label: 'Express tasks',
    icon: Zap,
    route: 'home',
    disabled: false,
    tooltipMessage: null,
    analyticsOption: 'express_tasks',
    authRequired: false,
  },
  {
    id: 2,
    label: 'Runtime',
    icon: CirclePlay,
    route: 'runtime',
    disabled: false,
    tooltipMessage: null,
    analyticsOption: 'runtime',
    authRequired: false,
  },
  {
    id: 4,
    label: 'Notebooks',
    icon: Notebook,
    route: 'notebooks',
    disabled: false,
    tooltipMessage: null,
    analyticsOption: 'notebook',
    authRequired: false,
  },
  {
    id: 5,
    label: 'Data Agent',
    icon: BotMessageSquare,
    route: 'data-agent',
    disabled: false,
    tooltipMessage: null,
    analyticsOption: 'data-agent',
    authRequired: false,
  },
  {
    id: 3,
    label: 'Orbits',
    icon: Orbit,
    route: 'orbits',
    disabled: false,
    tooltipMessage: null,
    analyticsOption: 'orbits',
    authRequired: true,
  },
]

export const SIDEBAR_MENU_BOTTOM = [
  {
    id: 2,
    label: 'Community',
    icon: MessageCircleCode,
    link: `https://discord.com/invite/qVPPstSv9R`,
  },
  {
    id: 1,
    label: 'Documentation',
    icon: File,
    link: `${import.meta.env.VITE_DOCS_URL}`,
  },
]

type IAppTaskData = TaskData & {
  isAvailable: boolean
}

const appTasks: IAppTaskData[] = [
  {
    id: 1,
    icon: TabularClassificationIcon,
    title: 'Tabular Classification',
    description:
      'Predict categories from table-structured data — ideal for tasks like customer segmentation, product classification, or fraud detection.',
    btnText: 'next',
    linkName: 'classification',
    tooltipData:
      'This task focuses on analyzing table-structured data to classify rows into predefined categories. Each row represents an observation, and the model uses the provided features (columns) to predict the target category.',
    isAvailable: true,
    analyticsTaskName: 'classification',
  },
  {
    id: 2,
    icon: TabularRegressionIcon,
    title: 'Tabular Regression',
    description:
      'Predict continuous numerical values from table-structured data — perfect for tasks like pricing or demand estimation.',
    btnText: 'next',
    linkName: 'regression',
    tooltipData:
      'This task involves analyzing table-structured data to predict continuous numerical values. Each row represents an observation, and the model uses the features (columns) to estimate the target variable.',
    isAvailable: true,
    analyticsTaskName: 'regression',
  },
  {
    id: 3,
    icon: ForecastingIcon,
    title: 'Time Series Forecasting',
    description:
      'Predict future values based on historical time-series data — ideal for tasks like sales projections, demand planning, or financial forecasting.',
    tooltipData:
      'This task focuses on analyzing historical time-series data to predict future trends or values over a specified period. It involves identifying patterns, seasonality, and trends in the data.',
    isAvailable: false,
    analyticsTaskName: '',
  },
  {
    id: 5,
    icon: ConversationalQAIcon,
    title: 'Prompt Optimization',
    description:
      'Construct and optimize LLM flows using a no-code builder — suitable for various NLP tasks, including text classification and structured information extraction.',
    btnText: 'next',
    tooltipData:
      'Define and automatically optimize generic LLM-based NLP pipelines using a no-code builder. Optimization can be performed either based on the task structure and description or on the provided labeled input-output pairs. ',
    isAvailable: true,
    analyticsTaskName: 'prompt_optimization',
  },
]

export const availableTasks = appTasks.filter((task) => task.isAvailable)
export const notAvailableTasks = appTasks.filter((task) => !task.isAvailable)

export const classificationResources = [
  {
    label: 'Data Cleaning Essentials',
    link: `${import.meta.env.VITE_DOCS_URL}/data-preparation`,
  },
  {
    label: 'Preparing Data for Classification',
    link: `${import.meta.env.VITE_DOCS_URL}/data-preparation`,
  },
  {
    label: 'Data Preparation Pitfalls',
    link: `${import.meta.env.VITE_DOCS_URL}/data-preparation`,
  },
]

export const regressionResources = [
  {
    label: 'Data Cleaning Essentials',
    link: `${import.meta.env.VITE_DOCS_URL}/data-preparation`,
  },
  {
    label: 'Preparing Data for Regression',
    link: `${import.meta.env.VITE_DOCS_URL}/data-preparation`,
  },
  {
    label: 'Data Preparation Pitfalls',
    link: `${import.meta.env.VITE_DOCS_URL}/data-preparation`,
  },
]

export const promptFusionResources = [
  {
    label: 'How to format your file',
    link: '#',
  },
  {
    label: 'Accepted field formats',
    link: '#',
  },
  {
    label: 'How to get your CSV',
    link: '#',
  },
]

export const tabularSteps = [
  {
    id: 1,
    text: 'Data Upload',
  },
  {
    id: 2,
    text: 'Data Preparation',
  },
  {
    id: 3,
    text: 'Model Evaluation',
  },
]
