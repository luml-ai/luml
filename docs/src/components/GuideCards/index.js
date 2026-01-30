import React from 'react';
import Link from '@docusaurus/Link';
import * as LucideIcons from 'lucide-react';
import styles from './styles.module.css';

function GuideCard({ icon, title, description, link, linkText }) {
  const IconComponent = LucideIcons[icon];

  return (
    <Link to={link} className={styles.card}>
      <div className={styles.icon}>
        {IconComponent ? <IconComponent size={32} /> : icon}
      </div>
      <h3 className={styles.title}>{title}</h3>
      <p className={styles.description}>{description}</p>
      <span className={styles.linkText}>{linkText || 'Learn more →'}</span>
    </Link>
  );
}

export default function GuideCards({ children }) {
  return <div className={styles.cardGrid}>{children}</div>;
}

export { GuideCard };