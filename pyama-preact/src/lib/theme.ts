// Theme management for dark mode
export function initTheme() {
  // Always apply dark mode class
  document.documentElement.classList.add('dark');
  
  // Also set it in localStorage to persist
  localStorage.setItem('theme', 'dark');
}

export function toggleTheme() {
  const isDark = document.documentElement.classList.contains('dark');
  if (isDark) {
    document.documentElement.classList.remove('dark');
    localStorage.setItem('theme', 'light');
  } else {
    document.documentElement.classList.add('dark');
    localStorage.setItem('theme', 'dark');
  }
}
