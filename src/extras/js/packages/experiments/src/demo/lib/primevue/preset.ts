import Aura from '@primevue/themes/aura'
import { definePreset } from '@primevue/themes'

export const dPreset = definePreset(Aura, {
  primitive: {
    blue: {
      550: '#2673FD',
    },
  },
  semantic: {
    colorScheme: {
      light: {
        primary: {
          color: '{blue.550}',
          50: '{blue.50}',
          100: '{blue.100}',
          200: '{blue.200}',
          300: '{blue.300}',
          400: '{blue.400}',
          500: '{blue.500}',
          600: '{blue.600}',
          700: '{blue.700}',
          800: '{blue.800}',
          900: '{blue.900}',
          950: '{blue.950}',
          hover: {
            color: '{primary.600}',
          },
          active: {
            color: '{primary.700}',
          },
        },
        surface: {
          0: '#fff',
          50: '{slate.50}',
          100: '{slate.100}',
          200: '{slate.200}',
          300: '{slate.300}',
          400: '{slate.400}',
          500: '{slate.500}',
          600: '{slate.600}',
          700: '{slate.700}',
          800: '{slate.800}',
          900: '{slate.900}',
          950: '{neutral.950}',
        },
      },
      dark: {
        primary: {
          color: '{blue.900}',
          50: '{blue.50}',
          100: '{blue.100}',
          200: '{blue.200}',
          300: '{blue.300}',
          400: '{blue.400}',
          500: '{blue.500}',
          600: '{blue.600}',
          700: '{blue.700}',
          800: '{blue.800}',
          900: '{blue.900}',
          950: '{blue.950}',
          hover: {
            color: '{primary.800}',
          },
          active: {
            color: '{primary.600}',
          },
        },
        surface: {
          0: '#fff',
          50: '{zinc.50}',
          100: '{zinc.100}',
          200: '{zinc.200}',
          300: '{zinc.300}',
          400: '{zinc.400}',
          500: '{zinc.500}',
          600: '{zinc.600}',
          700: '{zinc.700}',
          800: '{zinc.800}',
          900: '{zinc.900}',
          950: '{neutral.950}',
        },
      },
    },
  },
})
