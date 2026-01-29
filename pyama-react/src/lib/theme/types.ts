/**
 * Color definitions for a theme.
 * Each key maps to a CSS custom property (--color-{key}).
 */
export interface ThemeColors {
  // Core surfaces
  background: string;
  sidebar: string;
  foreground: string;
  'foreground-bright': string;

  // Cards & Popovers
  card: string;
  'card-foreground': string;
  popover: string;
  'popover-foreground': string;

  // Semantic colors
  primary: string;
  'primary-foreground': string;
  secondary: string;
  'secondary-foreground': string;
  muted: string;
  'muted-foreground': string;
  accent: string;
  'accent-foreground': string;
  destructive: string;
  'destructive-foreground': string;

  // Interactive elements
  border: string;
  input: string;
  ring: string;

  // Status colors
  success: string;
  'success-foreground': string;
  warning: string;
  'warning-foreground': string;
  info: string;
  'info-foreground': string;
}

/**
 * Complete theme definition.
 */
export interface Theme {
  /** Unique identifier (e.g., 'dark', 'light') */
  id: string;

  /** Human-readable name (e.g., 'Default Dark') */
  name: string;

  /** Theme type for system preference matching */
  type: 'dark' | 'light';

  /** Color definitions */
  colors: ThemeColors;

  /** Additional CSS variables (non-color) */
  variables?: {
    radius?: string;
    [key: string]: string | undefined;
  };
}

/**
 * Theme preference options.
 */
export type ThemePreference = 'light' | 'dark' | 'system';

/**
 * Theme state for the hook.
 */
export interface ThemeState {
  /** Current active theme */
  theme: Theme;

  /** User's preference (may differ from active when using 'system') */
  preference: ThemePreference;

  /** Resolved theme type (actual dark/light after system resolution) */
  resolvedType: 'dark' | 'light';
}
