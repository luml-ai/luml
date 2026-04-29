import { themes as prismThemes } from 'prism-react-renderer';
import type { Config } from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import dotenv from 'dotenv';

dotenv.config();

const config: Config = {
  title: 'LUML',
  tagline: 'Build AI Solutions Faster than Ever',
  favicon: 'img/favicon.svg',

  url: process.env.URL || 'https://luml.ai',
  baseUrl: '/',

  organizationName: 'LUML', 
  projectName: 'LUML', 

  onBrokenLinks: 'warn',
  onBrokenMarkdownLinks: 'warn',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

headTags: [],

  presets: [
    [
      'classic',
      {
        docs: {
          routeBasePath: '/', 
          sidebarPath: './sidebars.ts',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css', 
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/dsf.webp',
    colorMode: {
      defaultMode: 'light',
      disableSwitch: false,
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: '',
      logo: {
        alt: 'LUML Logo',
        src: 'https://gist.githubusercontent.com/OKUA1/1d730de58b9c7ccc3010d4e118552c5d/raw/379005eb32b69b6281e2c0be70fd82e5ef7bd456/luml_logo_full_black.svg',
        srcDark: 'https://gist.githubusercontent.com/OKUA1/1d730de58b9c7ccc3010d4e118552c5d/raw/379005eb32b69b6281e2c0be70fd82e5ef7bd456/luml_logo_full_white.svg',
        href: '/',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: 'Documentation',
        },
        // {
        //   type: 'docSidebar',
        //   sidebarId: 'guidesSidebar',
        //   position: 'left',
        //   label: 'Guides',
        //},
        {
          type: 'docSidebar',
          sidebarId: 'apiSidebar',
          position: 'left',
          label: 'API Reference',
        },
        {
          type: 'docSidebar',
          sidebarId: 'sdkSidebar',
          position: 'left',
          label: 'SDK',
        },
        {
          type: 'docSidebar',
          sidebarId: 'prismaSidebar',
          position: 'left',
          label: 'Prisma',
        },
        {
          href: 'https://github.com/luml-ai/luml',
          label: 'GitHub',
          position: 'right',
          className: 'navbar-github-link',
          'aria-label': 'GitHub',
        },
        {
          href: 'https://app.luml.ai',
          label: 'Get started',
          position: 'right',
          className: 'navbar__cta',
        },
      ],
    },
    footer: {
      style: 'light',
      links: [
        {
          title: 'Product',
          items: [
            {
              label: 'Documentation',
              to: '/documentation/quickstart',
            },
            {
              label: 'API Reference',
              to: '/api-reference/client/client',
            },
            {
              label: 'SDK',
              to: '/sdk/experiments/tracker',
            },
            {
              label: 'Pricing',
              href: 'https://luml.ai/#pricing',
            },
          ],
        },
        {
          title: 'Resources',
          items: [
            {
              label: 'Guides',
              to: '/guides/user_guidline',
            },
            {
              label: 'Blog',
              href: 'https://luml.ai/blog',
            },
            {
              label: 'Community',
              href: 'https://discord.com/invite/qVPPstSv9R',
            },
          ],
        },
        {
          title: 'Company',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/luml-ai/luml',
            },
            {
              label: 'About',
              href: 'https://dataforce.solutions',
            },
            {
              label: 'Contact',
              href: 'mailto:hi@dataforce.solutions',
            },
          ],
        },
      ],
      copyright: `© ${new Date().getFullYear()} LUML. All rights reserved.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;