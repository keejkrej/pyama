import type { Theme } from '../types';

export const lightTheme: Theme = {
  id: 'light',
  name: 'Default Light',
  type: 'light',
  colors: {
    // Core surfaces - clean whites with warm undertones
    background: '#fafaf9',
    sidebar: '#f5f5f4',
    foreground: 'hsl(0 0% 32%)',
    'foreground-bright': 'hsl(0 0% 9%)',

    // Cards & Popovers - slightly elevated
    card: '#ffffff',
    'card-foreground': 'hsl(0 0% 32%)',
    popover: '#ffffff',
    'popover-foreground': 'hsl(0 0% 20%)',

    // Primary - dark for light mode
    primary: 'hsl(0 0% 9%)',
    'primary-foreground': 'hsl(0 0% 98%)',

    // Secondary
    secondary: 'hsl(0 0% 85%)',
    'secondary-foreground': 'hsl(0 0% 20%)',

    // Muted
    muted: 'hsl(0 0% 92%)',
    'muted-foreground': 'hsl(0 0% 45%)',

    // Accent
    accent: 'hsl(0 0% 92%)',
    'accent-foreground': 'hsl(0 0% 20%)',

    // Destructive
    destructive: 'hsl(0 72% 51%)',
    'destructive-foreground': 'hsl(0 0% 98%)',

    // Interactive
    border: 'hsl(0 0% 82%)',
    input: '#ffffff',
    ring: 'hsl(0 0% 75%)',

    // Status
    success: 'hsl(142 71% 45%)',
    'success-foreground': 'hsl(0 0% 98%)',
    warning: 'hsl(38 92% 50%)',
    'warning-foreground': 'hsl(0 0% 10%)',
    info: 'hsl(217 91% 60%)',
    'info-foreground': 'hsl(0 0% 98%)',
  },
  variables: {
    radius: '0.5rem',
  },
};
