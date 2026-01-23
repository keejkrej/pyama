import type { ComponentChildren } from 'preact';

interface ButtonProps {
  children: ComponentChildren;
  onClick?: () => void;
  variant?: 'primary' | 'secondary' | 'ghost';
  className?: string;
  disabled?: boolean;
}

export function Button({
  children,
  onClick,
  variant = 'primary',
  className = '',
  disabled = false
}: ButtonProps) {
  const baseStyles = 'px-4 py-2 rounded-md font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed';

  const variantStyles = {
    primary: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500',
    secondary: 'bg-gray-200 text-gray-800 hover:bg-gray-300 focus:ring-gray-400 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600',
    ghost: 'bg-transparent text-gray-600 hover:bg-gray-100 focus:ring-gray-400 dark:text-gray-300 dark:hover:bg-gray-800',
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`${baseStyles} ${variantStyles[variant]} ${className}`}
    >
      {children}
    </button>
  );
}
