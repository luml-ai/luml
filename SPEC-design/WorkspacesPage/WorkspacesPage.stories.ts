import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { openFlows, openFlowsTotals, workspaceDirectory } from '@/fixtures/workspaces'
import {
  chartImageUrl,
  chartSvg,
  churnFeaturesTable,
  configJsonPretty,
  configJsonRaw,
  customersDatasetLuml,
  customersTable,
  edaReportHtml,
  experimentLuml,
  filesListed,
  forecasterLuml,
  moveTargets,
  paramsYaml,
  readmeMd,
  trainLog,
  trainPy,
} from './sample'
import WorkspacesPage from './WorkspacesPage.vue'

const dir = workspaceDirectory

const meta = {
  title: 'Proposals/UIP-002/WorkspacesPage',
  component: WorkspacesPage,
  args: { directory: dir, items: filesListed, openFlows, openFlowsTotals },
  parameters: {
    app: 'lumlflow',
    frame: { width: 1440, height: 900 },
    base: 'Pages/Lumlflow/WorkspacesPage',
    canvas: {
      rows: [
        { label: 'Listing', stories: ['FilesListed'] },
        {
          label: 'Text and code',
          stories: ['CodeFile', 'TextFile', 'YamlFile', 'JsonPretty', 'JsonRaw', 'MarkdownFile', 'MarkdownRaw'],
        },
        { label: 'Tables', stories: ['CsvFile', 'ParquetFile'] },
        {
          label: 'Media and documents',
          stories: ['ImageFile', 'SvgFile', 'PdfFile', 'HtmlFile', 'VideoFile', 'AudioFile'],
        },
        {
          label: 'LUML packages',
          stories: ['LumlModel', 'LumlExperiment', 'LumlDataset'],
        },
        { label: 'No preview', stories: ['NotPreviewable', 'TooLarge'] },
        {
          label: 'File operations',
          stories: ['FileMenuOpen', 'FileRenaming', 'MoveDialog', 'DeleteFileConfirm', 'DeleteFolderConfirm'],
        },
        { label: 'Create', stories: ['NewFolderDialog', 'NewFileDialog'] },
        { label: 'Editing', stories: ['EditingFile', 'EditConflict', 'AgentWorkingOnFile'] },
      ],
    },
  },
} satisfies Meta<typeof WorkspacesPage>

export default meta
type Story = StoryObj<typeof meta>

export const FilesListed: Story = { name: 'files listed, nothing open' }

export const CodeFile: Story = {
  name: 'code file (.py), highlighted',
  args: {
    viewer: {
      file: {
        name: 'train.py',
        path: `${dir}/train.py`,
        size: '2.31 KB',
        modified: '2026-11-04 16:42',
      },
      textContent: trainPy,
    },
  },
}

export const TextFile: Story = {
  name: 'plain text (.log), no highlighting',
  args: {
    viewer: {
      file: {
        name: 'train.log',
        path: `${dir}/train.log`,
        size: '1.96 KB',
        modified: '2026-11-04 16:42',
      },
      textContent: trainLog,
    },
  },
}

export const YamlFile: Story = {
  name: 'YAML file, pretty',
  args: {
    viewer: {
      file: {
        name: 'params.yaml',
        path: `${dir}/params.yaml`,
        size: '412 B',
        modified: '2026-11-03 11:20',
      },
      textContent: paramsYaml,
    },
  },
}

export const JsonPretty: Story = {
  name: 'JSON file, pretty',
  args: {
    viewer: {
      file: {
        name: 'config.json',
        path: `${dir}/config.json`,
        size: '638 B',
        modified: '2026-11-01 09:48',
      },
      textContent: configJsonRaw,
      prettyContent: configJsonPretty,
    },
  },
}

export const JsonRaw: Story = {
  name: 'JSON file, raw',
  args: {
    viewer: {
      file: {
        name: 'config.json',
        path: `${dir}/config.json`,
        size: '638 B',
        modified: '2026-11-01 09:48',
      },
      textContent: configJsonRaw,
      prettyContent: configJsonPretty,
      view: 'raw',
    },
  },
}

export const MarkdownFile: Story = {
  name: 'Markdown file, rendered',
  args: {
    viewer: {
      file: {
        name: 'README.md',
        path: `${dir}/README.md`,
        size: '1.84 KB',
        modified: '2026-11-02 10:15',
      },
      textContent: readmeMd,
    },
  },
}

export const MarkdownRaw: Story = {
  name: 'Markdown file, raw',
  args: {
    viewer: {
      file: {
        name: 'README.md',
        path: `${dir}/README.md`,
        size: '1.84 KB',
        modified: '2026-11-02 10:15',
      },
      textContent: readmeMd,
      view: 'raw',
    },
  },
}

export const CsvFile: Story = {
  name: 'table file (.csv)',
  args: {
    viewer: {
      file: {
        name: 'customers_sample.csv',
        path: `${dir}/customers_sample.csv`,
        size: '86 KB',
        modified: '2026-10-30 09:03',
      },
      table: customersTable,
    },
  },
}

export const ParquetFile: Story = {
  name: 'table file (.parquet)',
  args: {
    viewer: {
      file: {
        name: 'churn_features.parquet',
        path: `${dir}/churn_features.parquet`,
        size: '4.2 MB',
        modified: '2026-11-04 15:58',
      },
      table: churnFeaturesTable,
    },
  },
}

export const ImageFile: Story = {
  name: 'image (.png)',
  args: {
    viewer: {
      file: {
        name: 'roc_curve.png',
        path: `${dir}/roc_curve.png`,
        size: '48.2 KB',
        modified: '2026-11-04 16:50',
      },
      image: chartImageUrl,
    },
  },
}

export const SvgFile: Story = {
  name: 'vector image (.svg)',
  args: {
    viewer: {
      file: {
        name: 'feature_importance.svg',
        path: `${dir}/feature_importance.svg`,
        size: '9.4 KB',
        modified: '2026-11-04 16:51',
      },
      svg: chartSvg,
    },
  },
}

export const PdfFile: Story = {
  name: 'document (.pdf)',
  args: {
    viewer: {
      file: {
        name: 'model_report.pdf',
        path: `${dir}/model_report.pdf`,
        size: '312 KB',
        modified: '2026-11-04 17:05',
      },
      pdf: true,
    },
  },
}

export const HtmlFile: Story = {
  name: 'HTML report (.html)',
  args: {
    viewer: {
      file: {
        name: 'eda_report.html',
        path: `${dir}/eda_report.html`,
        size: '74 KB',
        modified: '2026-11-03 14:12',
      },
      html: edaReportHtml,
    },
  },
}

export const VideoFile: Story = {
  name: 'video (.mp4)',
  args: {
    viewer: {
      file: {
        name: 'demo_walkthrough.mp4',
        path: `${dir}/demo_walkthrough.mp4`,
        size: '18.4 MB',
        modified: '2026-10-28 13:30',
      },
      media: 'video',
    },
  },
}

export const AudioFile: Story = {
  name: 'audio (.wav)',
  args: {
    viewer: {
      file: {
        name: 'call_sample.wav',
        path: `${dir}/call_sample.wav`,
        size: '2.1 MB',
        modified: '2026-10-28 13:31',
      },
      media: 'audio',
    },
  },
}

export const NotPreviewable: Story = {
  name: 'no preview (.pkl)',
  args: {
    viewer: {
      file: {
        name: 'gbm_model.pkl',
        path: `${dir}/gbm_model.pkl`,
        size: '12.6 MB',
        modified: '2026-11-04 17:20',
      },
      previewState: 'unsupported',
    },
  },
}

export const TooLarge: Story = {
  name: 'too large for preview',
  args: {
    viewer: {
      file: {
        name: 'customers_sample.csv',
        path: `${dir}/customers_sample.csv`,
        size: '86 KB',
        modified: '2026-10-30 09:03',
      },
      previewState: 'too-big',
    },
  },
}

export const LumlModel: Story = {
  name: '.luml model',
  args: {
    viewer: {
      file: {
        name: 'demand_forecaster.luml',
        path: `${dir}/demand_forecaster.luml`,
        size: '2.4 MB',
        modified: '2026-11-04 18:05',
      },
      luml: forecasterLuml,
    },
  },
}

export const LumlExperiment: Story = {
  name: '.luml experiment',
  args: {
    viewer: {
      file: {
        name: 'churn_gbm_experiment.luml',
        path: `${dir}/churn_gbm_experiment.luml`,
        size: '3.4 MB',
        modified: '2026-11-04 18:02',
      },
      luml: experimentLuml,
    },
  },
}

export const LumlDataset: Story = {
  name: '.luml dataset',
  args: {
    viewer: {
      file: {
        name: 'customers.luml',
        path: `${dir}/customers.luml`,
        size: '5.1 MB',
        modified: '2026-11-04 18:10',
      },
      luml: customersDatasetLuml,
    },
  },
}

export const FileMenuOpen: Story = {
  name: 'file row menu open',
  args: { menuOpenId: `${dir}/train.py` },
}

export const FileRenaming: Story = {
  name: 'renaming a file',
  args: { renamingId: `${dir}/train.py`, renameValue: 'train_gbm.py' },
}

export const MoveDialog: Story = {
  name: 'move to… dialog',
  args: { dialog: 'move', dialogTarget: 'train.py', moveFolders: moveTargets, moveTo: 'archive' },
}

export const DeleteFileConfirm: Story = {
  name: 'delete file confirm',
  args: { dialog: 'delete-file', dialogTarget: 'customers_sample.csv' },
}

export const DeleteFolderConfirm: Story = {
  name: 'delete folder confirm',
  args: { dialog: 'delete-folder', dialogTarget: 'archive' },
}

export const NewFolderDialog: Story = {
  name: 'new folder dialog',
  args: { dialog: 'new-folder', dialogName: 'plots' },
}

export const EditingFile: Story = {
  name: 'editing a file',
  args: {
    viewer: {
      file: {
        name: 'train.py',
        path: `${dir}/train.py`,
        size: '2.31 KB',
        modified: '2026-11-04 16:42',
      },
      textContent: trainPy,
      editing: true,
    },
  },
}

export const EditConflict: Story = {
  name: 'editing, file changed on disk',
  args: {
    viewer: {
      file: {
        name: 'train.py',
        path: `${dir}/train.py`,
        size: '2.31 KB',
        modified: '2026-11-04 16:42',
      },
      textContent: trainPy,
      editing: true,
      conflict: true,
    },
  },
}

export const AgentWorkingOnFile: Story = {
  name: 'agent working on the file',
  args: {
    viewer: {
      file: {
        name: 'params.yaml',
        path: `${dir}/params.yaml`,
        size: '412 B',
        modified: '2026-11-04 16:58',
      },
      textContent: paramsYaml,
      agent: { label: 'Claude', color: '#d97706' },
    },
  },
}

export const NewFileDialog: Story = {
  name: 'new file dialog, name taken',
  args: { dialog: 'new-file', dialogName: 'README.md', dialogError: '"README.md" already exists' },
}
