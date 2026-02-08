import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'ESP32 Emu Turbo',
  tagline: 'Handheld retro gaming console powered by ESP32-S3',
  favicon: 'img/favicon.ico',

  future: {
    v4: true,
  },

  url: 'https://pjcau.github.io',
  baseUrl: '/esp32-emu-turbo/',

  organizationName: 'pjcau',
  projectName: 'esp32-emu-turbo',
  trailingSlash: false,

  onBrokenLinks: 'throw',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl:
            'https://github.com/pjcau/esp32-emu-turbo/tree/main/website/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/docusaurus-social-card.jpg',
    colorMode: {
      defaultMode: 'dark',
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'ESP32 Emu Turbo',
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'projectSidebar',
          position: 'left',
          label: 'Docs',
        },
        {
          href: 'https://github.com/pjcau/esp32-emu-turbo',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Documentation',
          items: [
            {
              label: 'Feasibility',
              to: '/docs/feasibility',
            },
            {
              label: 'Components (BOM)',
              to: '/docs/components',
            },
          ],
        },
        {
          title: 'Project',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/pjcau/esp32-emu-turbo',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} ESP32 Emu Turbo. Built with Docusaurus.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
