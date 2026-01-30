import React from 'react';
import Link from '@docusaurus/Link';
import {isActiveSidebarItem} from '@docusaurus/plugin-content-docs/client';
import type {Props} from '@theme/DocSidebarItem/Link';
import * as LucideIcons from 'lucide-react';

export default function DocSidebarItemLink({
  item,
  onItemClick,
  activePath,
  level,
  ...props
}: Props): JSX.Element {
  const {href, label, className, customProps} = item;
  const isActive = isActiveSidebarItem(item, activePath);
  const IconComponent = customProps?.icon
    ? LucideIcons[customProps.icon as keyof typeof LucideIcons]
    : null;

  return (
    <li
      className={className}
      key={label}>
      <Link
        className={
          isActive
            ? 'menu__link menu__link--active'
            : 'menu__link'
        }
        aria-current={isActive ? 'page' : undefined}
        to={href}
        {...(props as any)}
        onClick={onItemClick}>
        {IconComponent && (
          <IconComponent
            size={16}
            style={{
              marginRight: '8px',
              verticalAlign: 'middle',
              display: 'inline-block'
            }}
          />
        )}
        {label}
      </Link>
    </li>
  );
}
