import type { Theme } from '../types';
import { darkTheme } from './dark';
import { lightTheme } from './light';

/** Built-in themes */
export const builtInThemes: Record<string, Theme> = {
  dark: darkTheme,
  light: lightTheme,
};

/** Theme registry - can be extended with custom themes */
const themeRegistry = new Map<string, Theme>(Object.entries(builtInThemes));

export function getTheme(id: string): Theme | undefined {
  return themeRegistry.get(id);
}

export function getAllThemes(): Theme[] {
  return Array.from(themeRegistry.values());
}

export function registerTheme(theme: Theme): void {
  themeRegistry.set(theme.id, theme);
}

export function getThemesByType(type: 'dark' | 'light'): Theme[] {
  return getAllThemes().filter((t) => t.type === type);
}

export { darkTheme, lightTheme };
