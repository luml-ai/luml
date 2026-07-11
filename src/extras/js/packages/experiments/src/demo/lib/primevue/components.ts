import type { App } from 'vue'
import {
  Button,
  Card,
  InputText,
  Message,
  Popover,
  ToggleButton,
  FloatLabel,
  Dialog,
  Password,
  Menu,
  Avatar,
  Toast,
  FileUpload,
  IconField,
  InputIcon,
  ConfirmDialog,
  Badge,
  OverlayBadge,
  Divider,
  Select,
  RadioButton,
  Checkbox,
  ToggleSwitch,
} from 'primevue'
import { Form, FormField } from '@primevue/forms'

export const addComponents = (app: App) => {
  app.component('DButton', Button)
  app.component('DCard', Card)
  app.component('DInputText', InputText)
  app.component('DMessage', Message)
  app.component('DForm', Form)
  app.component('DFormField', FormField)
  app.component('DPopover', Popover)
  app.component('DToggleButton', ToggleButton)
  app.component('DFloatLabel', FloatLabel)
  app.component('DDialog', Dialog)
  app.component('DPassword', Password)
  app.component('DMenu', Menu)
  app.component('DAvatar', Avatar)
  app.component('DToast', Toast)
  app.component('DFileUpload', FileUpload)
  app.component('DIconField', IconField)
  app.component('DInputIcon', InputIcon)
  app.component('DConfirmDialog', ConfirmDialog)
  app.component('DBadge', Badge)
  app.component('DOverlayBadge', OverlayBadge)
  app.component('DDivider', Divider)
  app.component('DSelect', Select)
  app.component('DRadioButton', RadioButton)
  app.component('DCheckbox', Checkbox)
  app.component('DToggleSwitch', ToggleSwitch)
}
