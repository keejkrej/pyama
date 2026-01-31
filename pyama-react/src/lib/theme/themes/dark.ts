import type { Theme } from "../types";

export const darkTheme: Theme = {
  id: "dark",
  name: "Default Dark",
  type: "dark",
  colors: {
    // Core surfaces - warm dark tones
    background: "#14120b",
    sidebar: "#0f0e08",
    foreground: "hsl(0 0% 70%)",
    "foreground-bright": "hsl(0 0% 95%)",

    // Cards & Popovers
    card: "#1b1a16",
    "card-foreground": "hsl(0 0% 70%)",
    popover: "#1b1a16",
    "popover-foreground": "hsl(0 0% 85%)",

    // Primary - high contrast white
    primary: "hsl(0 0% 95%)",
    "primary-foreground": "hsl(0 0% 10%)",

    // Secondary - muted gray
    secondary: "hsl(0 0% 52%)",
    "secondary-foreground": "hsl(0 0% 85%)",

    // Muted
    muted: "hsl(0 0% 50%)",
    "muted-foreground": "hsl(0 0% 55%)",

    // Accent
    accent: "hsl(0 0% 52%)",
    "accent-foreground": "hsl(0 0% 85%)",

    // Destructive - red
    destructive: "hsl(0 62.8% 30.6%)",
    "destructive-foreground": "hsl(0 0% 98%)",

    // Interactive
    border: "hsl(0 0% 42%)",
    input: "#22211d",
    ring: "hsl(0 0% 12%)",

    // Status
    success: "hsl(142 76% 36%)",
    "success-foreground": "hsl(0 0% 98%)",
    warning: "hsl(38 92% 50%)",
    "warning-foreground": "hsl(0 0% 10%)",
    info: "hsl(217 91% 60%)",
    "info-foreground": "hsl(0 0% 98%)",
  },
  variables: {
    radius: "0.5rem",
  },
};
