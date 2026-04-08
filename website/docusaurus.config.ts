import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'ESP32 Emu Turbo',
  tagline: 'SNES-first handheld retro gaming console powered by ESP32-S3',
  favicon: 'img/favicon.ico',

  future: {
    v4: true,
  },

  markdown: {
    mermaid: true,
  },
  themes: ['@docusaurus/theme-mermaid'],

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
      logo: {
        alt: 'ESP32 Emu Turbo Logo',
        src: 'img/logo.svg',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'projectSidebar',
          position: 'left',
          label: 'Docs',
        },
        {
          href: 'pathname:///viewer.html',
          label: '3D Viewer',
          position: 'left',
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
          title: 'Design',
          items: [
            {
              label: 'Feasibility',
              to: '/docs/overview/feasibility',
            },
            {
              label: 'Schematics',
              to: '/docs/design/schematics',
            },
            {
              label: 'PCB Layout',
              to: '/docs/design/pcb',
            },
            {
              label: 'Components (BOM)',
              to: '/docs/design/components',
            },
          ],
        },
        {
          title: 'Build',
          items: [
            {
              label: 'Manufacturing',
              to: '/docs/manufacturing',
            },
            {
              label: 'Verification',
              to: '/docs/manufacturing/verification',
            },
            {
              label: 'Software',
              to: '/docs/software',
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
