import type { TaskData } from '@/components/homepage-tasks/interfaces'
import {
  Zap,
  File,
  Orbit,
  MessageCircleCode,
  Folders,
  Pyramid,
  Rocket,
  Satellite,
  ChartSpline,
} from 'lucide-vue-next'
import TabularClassificationIcon from '@/assets/img/cards-icons/tabular-classification.svg'
import TabularRegressionIcon from '@/assets/img/cards-icons/tabular-regression.svg'
import ForecastingIcon from '@/assets/img/cards-icons/forecasting.svg'
import ConversationalQAIcon from '@/assets/img/cards-icons/conversational-qa.svg'
import Notebooks from '@/assets/img/cards-icons/notebook.svg'

export const SIDEBAR_SECTIONS = [
  {
    id: 'core',
    label: 'Core',
    items: [
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
        id: 6,
        label: 'Registry',
        icon: Folders,
        route: 'orbit-registry',
        disabled: false,
        tooltipMessage: null,
        analyticsOption: 'orbit-registry',
        authRequired: false,
      },
      {
        id: 7,
        label: 'Deployments',
        icon: Rocket,
        route: 'orbit-deployments',
        disabled: false,
        tooltipMessage: null,
        analyticsOption: 'orbit-deployments',
        authRequired: false,
      },
      {
        id: 8,
        label: 'Satellites',
        icon: Satellite,
        route: 'orbit-satellites',
        disabled: false,
        tooltipMessage: null,
        analyticsOption: 'orbit-satellites',
        authRequired: false,
      },
    ],
  },
  {
    id: 'apps',
    label: 'Apps',
    items: [
      {
        id: 5,
        label: 'Prisma',
        icon: Pyramid,
        route: 'prisma-board',
        disabled: false,
        tooltipMessage: null,
        analyticsOption: 'prisma',
        authRequired: false,
      },
      {
        id: 9,
        label: 'Flow',
        icon: ChartSpline,
        route: 'flow',
        disabled: false,
        tooltipMessage: null,
        analyticsOption: 'flow',
        authRequired: false,
      },
    ],
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
    dropdownOptions: [
      { label: 'Train new model' },
      { label: 'Upload for inference', route: 'runtime' },
    ],
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
    dropdownOptions: [
      { label: 'Train new model' },
      { label: 'Upload for inference', route: 'runtime' },
    ],
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
    dropdownOptions: [
      { label: 'Train new model' },
      { label: 'Upload for inference', route: 'runtime' },
    ],
  },
  {
    id: 4,
    icon: Notebooks,
    title: 'Notebooks',
    description:
      'Run Jupyter notebooks directly in the browser with no setup or backend. Create, test, and export models locally with automatic discovery, while managing instances entirely client-side.',
    btnText: 'next',
    linkName: 'notebooks',
    tooltipData:
      'Run Jupyter notebooks fully in the browser using a WebAssembly-based Python runtime with no backend or setup required. All data is stored locally in the browser, with options to export, back up, and automatically surface saved models in the platform UI.',
    isAvailable: true,
    analyticsTaskName: 'notebook',
  },

  {
    id: 3,
    icon: ForecastingIcon,
    title: 'Time Series Forecasting',
    description:
      'Predict future values based on historical time-series data — ideal for tasks like sales projections, demand planning, or financial forecasting.',
    btnText: 'coming soon',
    tooltipData:
      'This task focuses on analyzing historical time-series data to predict future trends or values over a specified period. It involves identifying patterns, seasonality, and trends in the data.',
    isAvailable: true,
    isDisabled: true,
    analyticsTaskName: '',
  },
]

export const availableTasks = appTasks.filter((task) => task.isAvailable)

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
