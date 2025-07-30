import React, { useState, Children, cloneElement } from "react";
import { motion } from "motion/react";
import DotSlashLogo from '../../assets/dotSlash.svg';
import { FaBars, FaTimes } from 'react-icons/fa';

const transition = {
  type: "spring",
  mass: 0.5,
  damping: 11.5,
  stiffness: 100,
  restDelta: 0.001,
  restSpeed: 0.001,
};

export const MenuItem = ({
  setActive,
  active,
  item,
  children
}) => {
  return (
    <div onMouseEnter={() => setActive(item)} className="relative">
      <motion.p
        transition={{ duration: 0.3 }}
        className="cursor-pointer text-black hover:opacity-[0.9] dark:text-white px-3 py-2 rounded-md text-sm font-medium">
        {item}
      </motion.p>
      {active !== null && (
        <motion.div
          initial={{ opacity: 0, scale: 0.85, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={transition}>
          {active === item && (
            <div className="absolute top-[calc(100%_+_0.5rem)] left-1/2 transform -translate-x-1/2 pt-4">
              <motion.div
                transition={transition}
                layoutId={`active-menu-item-${item}`}
                className="bg-white dark:bg-black backdrop-blur-sm rounded-2xl overflow-hidden border border-black/[0.2] dark:border-white/[0.2] shadow-xl">
                <motion.div layout className="w-max h-full p-4">
                  {children}
                </motion.div>
              </motion.div>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
};

export const Menu = ({
  setActive,
  children
}) => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Extract links for mobile menu
  // Helper function to extract a link element from a MenuItem's children
  const extractLinkElement = (menuItemChildren) => {
    return Children.toArray(menuItemChildren).find(
      child => child.type === HoveredLink || (child.props && child.props.href) // Look for HoveredLink or a direct href
    );
  };

  // Helper function to extract a mobile link from a MenuItem
  const extractMobileLink = (menuItem) => {
    if (menuItem.props && menuItem.props.item && menuItem.props.children) {
      const linkElement = extractLinkElement(menuItem.props.children);
      if (linkElement && linkElement.props && linkElement.props.href) {
        return {
          name: menuItem.props.item,
          href: linkElement.props.href,
          onClick: linkElement.props.onClick // Preserve onClick for logout, etc.
        };
      }
    }
    return null;
  };

  // Extract links for the mobile menu
  const mobileLinks = Children.map(children, extractMobileLink).filter(Boolean);
  return (
    <>
      <nav
        onMouseLeave={() => {
          setActive(null);
          // Do not close mobile menu on mouse leave, only by toggle or link click
        }}
        className="fixed top-4 left-1/2 transform -translate-x-1/2 w-[90vw] md:w-[60vw] max-w-4xl z-50 rounded-full border border-transparent dark:border-white/[0.2] bg-white/80 dark:bg-black/80 backdrop-blur-md shadow-input flex items-center justify-between px-4 py-3"
      >
        <img src={DotSlashLogo} alt="Logo" className="h-8 w-auto" />

        {/* Desktop Menu Items */}
        <div className="hidden md:flex flex-grow justify-center space-x-2 md:space-x-4">
          {children}
        </div>

        {/* Mobile Menu Toggle */}
        <div className="md:hidden">
          <button onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)} className="text-black dark:text-white">
            {isMobileMenuOpen ? <FaTimes size={24} /> : <FaBars size={24} />}
          </button>
        </div>
      </nav>

      {/* Mobile Menu Overlay */}
      {isMobileMenuOpen && (
        <div className="md:hidden fixed inset-0 top-16 bg-white/90 dark:bg-black/90 backdrop-blur-lg z-40 pt-10">
          <ul className="flex flex-col items-center space-y-4 p-4">
            {mobileLinks.map((link, index) => (
              <li key={index} className="w-full text-center">
                <a
                  href={link.href}
                  onClick={(e) => {
                    if (link.onClick) link.onClick(e);
                    setIsMobileMenuOpen(false); // Close menu on link click
                  }}
                  className="text-lg text-neutral-700 dark:text-neutral-200 hover:text-soda-blue dark:hover:text-soda-blue py-3 block w-full rounded-md"
                >
                  {link.name}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
};

export const ProductItem = ({
  title,
  description,
  href,
  src
}) => {
  return (
    <a href={href} className="flex space-x-2">
      <img
        src={src}
        width={140}
        height={70}
        alt={title}
        className="flex-shrink-0 rounded-md shadow-2xl" />
      <div>
        <h4 className="text-xl font-bold mb-1 text-black dark:text-white">
          {title}
        </h4>
        <p className="text-neutral-700 text-sm max-w-[10rem] dark:text-neutral-300">
          {description}
        </p>
      </div>
    </a>
  );
};

export const HoveredLink = ({
  children,
  ...rest
}) => {
  return (
    <a {...rest} className="text-neutral-700 dark:text-neutral-200 hover:text-black dark:hover:text-soda-blue p-2 rounded-md">
      {children}
    </a>
  );
};
