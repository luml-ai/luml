import { themes as prismThemes } from 'prism-react-renderer';
import type { Config } from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import dotenv from 'dotenv';

dotenv.config();

const config: Config = {
  title: 'DataForce Studio',
  tagline: 'Build AI Solutions Faster than Ever',
  favicon: 'img/favicon.ico',

  url: process.env.URL || 'https://dataforce.studio',
  baseUrl: '/',

  organizationName: 'DataForce', 
  projectName: 'DataForce Studio', 

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
      title: 'DataForce Studio', 
      
      logo: {
        alt: 'DataForce Studio Logo',
        src: 'img/logo.png',
        href: '/', 
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar', 
          position: 'left',
          label: 'Documentation',
        },
        {
          type: 'docSidebar',
          sidebarId: 'guidesSidebar', 
          position: 'left',
          label: 'Guides',
        },
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
              to: '/documentation/intro', 
            },
            {
              label: 'Guides',
              to: '/guides/getting-started', 
            },
            {
              label: 'SDK',
              to: '/sdk/reference/dataforce/api', 
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} DataForce Solutions GmbH. All rights reserved.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
    announcementBar: {
      id: 'wip_notice', 
      content: '🚧 This documentation is a work in progress.',
      backgroundColor: '#fff3cd', 
      textColor: '#663c00',       
      isCloseable: true,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;