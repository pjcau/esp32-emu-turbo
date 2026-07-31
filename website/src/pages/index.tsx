import type {ReactNode} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';

import styles from './index.module.css';

function HomepageHeader() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <header className={clsx('hero hero--primary', styles.heroBanner)}>
      <div className="container">
        <Heading as="h1" className="hero__title">
          {siteConfig.title}
        </Heading>
        <p className="hero__subtitle">{siteConfig.tagline}</p>
        <div className={styles.buttons}>
          <Link className="button button--secondary button--lg" to="/docs/">
            View Documentation
          </Link>
          <Link
            className="button button--outline button--secondary button--lg"
            href="pathname:///net-explorer.html">
            Explore the PCB
          </Link>
        </div>
      </div>
    </header>
  );
}

type FeatureItem = {
  title: string;
  description: string;
};

const features: FeatureItem[] = [
  {
    title: 'SNES + NES',
    description:
      'SNES-first retro game emulation on ESP32-S3 with SIMD/PIE and 8MB Octal PSRAM.',
  },
  {
    title: 'Portable',
    description:
      'Rechargeable LiPo battery with USB-C charging and a 3.95" 320x480 parallel TFT display.',
  },
  {
    title: 'Open Source',
    description:
      'Fully open source hardware and software. Schematics, PCB design, firmware and 3D models included.',
  },
];

type CardItem = {
  title: string;
  description: string;
  to?: string;
  href?: string;
};

const tools: CardItem[] = [
  {
    title: 'Net Explorer',
    description:
      'Interactive board viewer: components by side and layer, per-pin “where does this go”, full net membership and trace paths.',
    href: 'pathname:///net-explorer.html',
  },
  {
    title: 'Interactive BOM',
    description:
      'Visual assembly aid — click a BOM row and the part lights up on the board. Generated from the live .kicad_pcb.',
    href: 'pathname:///ibom/ibom.html',
  },
  {
    title: '3D Viewer',
    description:
      'Photorealistic raytraced renders of the PCBA and the OpenSCAD enclosure, straight from the design files.',
    href: 'pathname:///viewer.html',
  },
];

const docSections: CardItem[] = [
  {
    title: 'Hardware Design',
    description:
      'Schematics, PCB layout, GPIO mapping and the full component BOM with LCSC part numbers.',
    to: '/docs/design/schematics',
  },
  {
    title: 'Manufacturing & Verification',
    description:
      '124-test DFM suite, DFA, JLCPCB rules, KiBot CI — every commit is checked before it can ship.',
    to: '/docs/manufacturing',
  },
  {
    title: 'Rework & Incidents',
    description:
      'Honest post-mortems of real fabrication bugs — including the v4.3.1 systemic rotation error — and what now guards against each.',
    to: '/docs/rework/incident-v431-rotations',
  },
  {
    title: 'Virtual Bench',
    description:
      'Simulation-first hardware debugging: SPICE models and analyses standing in for the bench instruments we do not have.',
    to: '/docs/vbench/virtual-bench',
  },
  {
    title: 'Software',
    description:
      'ESP-IDF v5.x firmware: display driver, controls, SD card ROM loading and the emulator bring-up plan.',
    to: '/docs/software',
  },
  {
    title: 'Tooling',
    description:
      'The Claude Code agent/skill architecture and the KiCad + JLCPCB ecosystem analysis behind the pipeline.',
    to: '/docs/tooling/ecosystem-analysis',
  },
];

function Card({title, description, to, href}: CardItem) {
  return (
    <div className="col col--4 margin-bottom--lg">
      <Link to={to} href={href} className={clsx('card', styles.card)}>
        <div className="card__header">
          <Heading as="h3">{title}</Heading>
        </div>
        <div className="card__body">
          <p>{description}</p>
        </div>
      </Link>
    </div>
  );
}

export default function Home(): ReactNode {
  return (
    <Layout
      title="Home"
      description="SNES-first handheld retro gaming console powered by ESP32-S3">
      <HomepageHeader />
      <main>
        <section className={styles.section}>
          <div className="container">
            <div className="row">
              {features.map((f) => (
                <div key={f.title} className="col col--4">
                  <div className={styles.feature}>
                    <Heading as="h3">{f.title}</Heading>
                    <p>{f.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className={clsx(styles.section, styles.sectionAlt)}>
          <div className="container">
            <Heading as="h2" className={styles.sectionTitle}>
              Interactive tools
            </Heading>
            <p className={styles.sectionSubtitle}>
              Generated from the live design files on every change — never
              hand-maintained.
            </p>
            <div className="row">
              {tools.map((t) => (
                <Card key={t.title} {...t} />
              ))}
            </div>
          </div>
        </section>

        <section className={styles.section}>
          <div className="container">
            <Heading as="h2" className={styles.sectionTitle}>
              Explore the documentation
            </Heading>
            <div className="row">
              {docSections.map((d) => (
                <Card key={d.title} {...d} />
              ))}
            </div>
          </div>
        </section>
      </main>
    </Layout>
  );
}
