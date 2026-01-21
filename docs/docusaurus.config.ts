import { themes as prismThemes } from 'prism-react-renderer';
import type { Config } from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import dotenv from 'dotenv';

dotenv.config();

const config: Config = {
  title: 'LUML',
  tagline: 'Build AI Solutions Faster than Ever',
  favicon: 'https://gist.githubusercontent.com/OKUA1/1d730de58b9c7ccc3010d4e118552c5d/raw/e6d2b6ff16759b6e2021e1a57e0427c722dd5adc/luml_logo_mark_black.svg',

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
          sidebarId: 'sdkSidebar', 
          position: 'left',
          label: 'SDK',
        },
      ],
    },
    footer: {
      style: 'light',
      links: [
        {
          title: 'Docs',
          items: [
            {
              label: 'Documentation',
              to: '/documentation/quickstart', 
            },
            {
              label: 'Guides',
              to: '/guides/user_guidline', 
            },
            {
              label: 'SDK',
              to: '/sdk/bucket-secrets', 
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} LUML. All rights reserved.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
    // announcementBar: {
    //   id: 'wip_notice', 
    //   content: '🚧 This documentation is a work in progress.',
    //   backgroundColor: '#fff3cd', 
    //   textColor: '#663c00',       
    //   isCloseable: true,
    // },
  } satisfies Preset.ThemeConfig,
};

export default config;