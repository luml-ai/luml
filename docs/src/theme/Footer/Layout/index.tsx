import React, {type ReactNode} from 'react';
import type {Props} from '@theme/Footer/Layout';

import styles from './styles.module.css';

export default function FooterLayout({
  links,
  logo,
  copyright,
}: Props): ReactNode {
  return (
    <footer className={styles.footer}>
      <div className={styles.footerContainer}>
        <div className={styles.footerPanel}>
          {/* Link columns */}
          <div className={styles.footerColumns}>
            {links}
          </div>
          {/* Bottom bar */}
          {(logo || copyright) && (
            <div className={styles.footerBottom}>
              {logo && <div>{logo}</div>}
              {copyright}
            </div>
          )}
        </div>
      </div>
    </footer>
  );
}
