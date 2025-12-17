export const theme = {
  // Colors
  colors: {
    primary: {
      dark: '#1a1a2e',
      navy: '#16213e',
      navyAlt: '#0f3460',
      gold: '#d4af37',
      goldAlt: '#e5c04b',
    },
    backgrounds: {
      primary: '#1a1a2e',
      secondary: '#16213e',
      tertiary: '#0f3460',
      hover: 'rgba(212, 175, 55, 0.1)',
      active: 'rgba(212, 175, 55, 0.2)',
    },
    text: {
      primary: '#ffffff',
      secondary: '#b0b0b0',
      tertiary: '#808080',
      accent: '#d4af37',
      accentAlt: '#e5c04b',
    },
    borders: {
      light: 'rgba(212, 175, 55, 0.3)',
      medium: 'rgba(212, 175, 55, 0.5)',
      dark: 'rgba(212, 175, 55, 0.7)',
    },
    status: {
      success: '#4caf50',
      warning: '#ff9800',
      error: '#f44336',
      info: '#2196f3',
    },
  },

  // Shadows
  shadows: {
    sm: '0 1px 3px rgba(0, 0, 0, 0.3)',
    md: '0 4px 8px rgba(0, 0, 0, 0.4)',
    lg: '0 8px 16px rgba(0, 0, 0, 0.5)',
    xl: '0 12px 24px rgba(0, 0, 0, 0.6)',
    glow: '0 0 8px rgba(212, 175, 55, 0.3), 0 0 16px rgba(212, 175, 55, 0.15)',
    glowHover: '0 0 16px rgba(212, 175, 55, 0.5), 0 0 24px rgba(212, 175, 55, 0.2)',
  },

  // Gradients
  gradients: {
    primary: 'linear-gradient(135deg, #16213e 0%, #0f3460 100%)',
    gold: 'linear-gradient(135deg, #d4af37 0%, #e5c04b 100%)',
    accent: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)',
    lightAccent: 'linear-gradient(135deg, rgba(212, 175, 55, 0.1), rgba(229, 192, 75, 0.1))',
  },

  // Spacing
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    xxl: '48px',
  },

  // Typography
  typography: {
    fontFamily: {
      primary: '"Segoe UI", Tahoma, Geneva, Verdana, sans-serif',
      mono: '"Courier New", monospace',
    },
    fontSize: {
      xs: '12px',
      sm: '14px',
      base: '16px',
      lg: '18px',
      xl: '20px',
      xxl: '24px',
      xxxl: '32px',
    },
    fontWeight: {
      light: 300,
      normal: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
    },
  },

  // Border Radius
  borderRadius: {
    none: '0',
    sm: '4px',
    md: '8px',
    lg: '12px',
    xl: '16px',
    full: '9999px',
  },

  // Transitions
  transitions: {
    fast: '150ms ease-in-out',
    base: '250ms ease-in-out',
    slow: '350ms ease-in-out',
  },

  // Component-specific styles
  components: {
    button: {
      primary: {
        background: 'linear-gradient(135deg, #d4af37 0%, #e5c04b 100%)',
        color: '#1a1a2e',
        border: 'none',
        borderRadius: '8px',
        padding: '10px 20px',
        fontSize: '14px',
        fontWeight: 600,
        cursor: 'pointer',
        transition: 'all 250ms ease-in-out',
        boxShadow: '0 4px 8px rgba(0, 0, 0, 0.3)',
      },
      primaryHover: {
        boxShadow: '0 0 16px rgba(212, 175, 55, 0.5), 0 0 24px rgba(212, 175, 55, 0.2)',
        transform: 'translateY(-2px)',
      },
      secondary: {
        background: 'transparent',
        color: '#d4af37',
        border: '2px solid rgba(212, 175, 55, 0.5)',
        borderRadius: '8px',
        padding: '8px 18px',
        fontSize: '14px',
        fontWeight: 600,
        cursor: 'pointer',
        transition: 'all 250ms ease-in-out',
      },
      secondaryHover: {
        borderColor: '#d4af37',
        boxShadow: '0 0 12px rgba(212, 175, 55, 0.3)',
      },
    },
    input: {
      background: '#0f3460',
      border: '2px solid rgba(212, 175, 55, 0.3)',
      color: '#ffffff',
      borderRadius: '8px',
      padding: '10px 14px',
      fontSize: '14px',
      transition: 'all 250ms ease-in-out',
      placeholder: '#808080',
    },
    inputFocus: {
      borderColor: '#d4af37',
      boxShadow: '0 0 8px rgba(212, 175, 55, 0.3)',
      outline: 'none',
    },
    card: {
      background: '#16213e',
      border: '1px solid rgba(212, 175, 55, 0.2)',
      borderRadius: '12px',
      padding: '20px',
      boxShadow: '0 4px 8px rgba(0, 0, 0, 0.3)',
      transition: 'all 250ms ease-in-out',
    },
    cardHover: {
      borderColor: 'rgba(212, 175, 55, 0.5)',
      boxShadow: '0 8px 16px rgba(0, 0, 0, 0.5), 0 0 12px rgba(212, 175, 55, 0.2)',
      transform: 'translateY(-4px)',
    },
    badge: {
      background: 'linear-gradient(135deg, #d4af37 0%, #e5c04b 100%)',
      color: '#1a1a2e',
      borderRadius: '20px',
      padding: '6px 12px',
      fontSize: '12px',
      fontWeight: 600,
    },
    link: {
      color: '#d4af37',
      textDecoration: 'none',
      transition: 'all 250ms ease-in-out',
    },
    linkHover: {
      color: '#e5c04b',
      textDecoration: 'underline',
    },
  },

  // Responsive breakpoints
  breakpoints: {
    mobile: '480px',
    tablet: '768px',
    desktop: '1024px',
    wide: '1440px',
    ultraWide: '1920px',
  },
};

export default theme;
