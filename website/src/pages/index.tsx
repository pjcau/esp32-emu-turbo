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
          <Link
            className="button button--secondary button--lg"
            to="/docs/">
            View Documentation
          </Link>
        </div>
      </div>
    </header>
  );
}

export default function Home(): ReactNode {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout
      title="Home"
      description="Handheld retro gaming console powered by ESP32-S3 - NES and SNES emulation">
      <HomepageHeader />
      <main>
        <section style={{padding: '2rem 0'}}>
          <div className="container">
            <div className="row">
              <div className="col col--4">
                <div style={{textAlign: 'center', padding: '1rem'}}>
                  <Heading as="h3">NES + SNES</Heading>
                  <p>Retro game emulation on ESP32-S3 hardware with Octal PSRAM and SIMD instructions.</p>
                </div>
              </div>
              <div className="col col--4">
                <div style={{textAlign: 'center', padding: '1rem'}}>
                  <Heading as="h3">Portable</Heading>
                  <p>Rechargeable LiPo battery with USB-C charging and a 3.5"-4" color TFT/LCD display.</p>
                </div>
              </div>
              <div className="col col--4">
                <div style={{textAlign: 'center', padding: '1rem'}}>
                  <Heading as="h3">Open Source</Heading>
                  <p>Fully open source hardware and software. Schematics, PCB designs, and 3D models included.</p>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
    </Layout>
  );
}
