import React, {type ComponentProps, useEffect, useMemo} from 'react';
import clsx from 'clsx';
import {
  ThemeClassNames,
  useThemeConfig,
  usePrevious,
  Collapsible,
  useCollapsible,
} from '@docusaurus/theme-common';
import {
  isActiveSidebarItem,
  findFirstSidebarItemLink,
  useDocSidebarItemsExpandedState,
} from '@docusaurus/plugin-content-docs/client';
import Link from '@docusaurus/Link';
import {translate} from '@docusaurus/Translate';
import useIsBrowser from '@docusaurus/useIsBrowser';
import DocSidebarItems from '@theme/DocSidebarItems';
import type {Props} from '@theme/DocSidebarItem/Category';
import * as LucideIcons from 'lucide-react';

function usePrevCollapsed(collapsed: boolean): boolean | undefined {
  const prevCollapsed = usePrevious(collapsed);
  return prevCollapsed ?? collapsed;
}

function isSamePath(path1: string | undefined, path2: string | undefined): boolean {
  if (!path1 || !path2) {
    return false;
  }
  return path1 === path2;
}

function DocSidebarItemCategory({
  item,
  onItemClick,
  activePath,
  level,
  index,
  ...props
}: Props): JSX.Element {
  const {items, label, collapsible, className, href, customProps} = item;
  const {
    docs: {
      sidebar: {autoCollapseCategories},
    },
  } = useThemeConfig();
  const hrefWithSSR = useIsBrowser() ? href : undefined;
  const isActive = isActiveSidebarItem(item, activePath);
  const isCurrentPage = isSamePath(href, activePath);

  const {collapsed, setCollapsed} = useCollapsible({
    initialState: () => {
      if (!collapsible) {
        return false;
      }
      return !isActive;
    },
  });

  const prevCollapsed = usePrevCollapsed(collapsed);

  const {expandedItem, setExpandedItem} = useDocSidebarItemsExpandedState();
  function updateCollapsed(toCollapsed: boolean = !collapsed) {
    setExpandedItem(toCollapsed ? null : index);
    setCollapsed(toCollapsed);
  }
  useEffect(() => {
    if (
      collapsible &&
      expandedItem != null &&
      expandedItem !== index &&
      autoCollapseCategories
    ) {
      setCollapsed(true);
    }
  }, [collapsible, expandedItem, index, setCollapsed, autoCollapseCategories]);

  const IconComponent = customProps?.icon
    ? LucideIcons[customProps.icon as keyof typeof LucideIcons]
    : null;

  return (
    <li
      className={clsx(
        ThemeClassNames.docs.docSidebarItemCategory,
        ThemeClassNames.docs.docSidebarItemCategoryLevel(level),
        'menu__list-item',
        {
          'menu__list-item--collapsed': collapsed,
        },
        className,
      )}>
      <div
        className={clsx('menu__list-item-collapsible', {
          'menu__list-item-collapsible--active': isCurrentPage,
        })}>
        <Link
          className={clsx('menu__link', {
            'menu__link--sublist': collapsible && items.length > 0,
            'menu__link--sublist-caret': collapsible && items.length > 0,
            'menu__link--active': isActive,
          })}
          onClick={
            collapsible
              ? (e) => {
                  onItemClick?.(item);
                  if (!href) {
                    e.preventDefault();
                  }
                  updateCollapsed();
                }
              : () => {
                  onItemClick?.(item);
                }
          }
          aria-current={isCurrentPage ? 'page' : undefined}
          role={collapsible && !href ? 'button' : undefined}
          aria-expanded={collapsible && !href ? !collapsed : undefined}
          href={collapsible ? hrefWithSSR ?? '#' : hrefWithSSR}
          {...props}>
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
      </div>

      <Collapsible lazy as="ul" className="menu__list" collapsed={collapsed}>
        <DocSidebarItems
          items={items}
          tabIndex={collapsed ? -1 : 0}
          onItemClick={onItemClick}
          activePath={activePath}
          level={level + 1}
        />
      </Collapsible>
    </li>
  );
}

export default React.memo(DocSidebarItemCategory);
