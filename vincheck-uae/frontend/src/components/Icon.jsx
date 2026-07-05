// Minimal inline icon set — avoids pulling in a full icon library for a handful of glyphs.
export function Icon({ name, size = 16, className = '' }) {
  const props = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    className,
  };

  switch (name) {
    case 'car':
      return (
        <svg {...props}>
          <path d="M3 13l1.5-4.5A2 2 0 0 1 6.4 7h11.2a2 2 0 0 1 1.9 1.5L21 13" />
          <rect x="3" y="13" width="18" height="5" rx="1.5" />
          <circle cx="7.5" cy="18.5" r="1.5" />
          <circle cx="16.5" cy="18.5" r="1.5" />
        </svg>
      );
    case 'layout':
      return (
        <svg {...props}>
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path d="M9 3v18" />
        </svg>
      );
    case 'world':
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="9" />
          <path d="M3 12h18M12 3a13 13 0 0 1 0 18 13 13 0 0 1 0-18Z" />
        </svg>
      );
    case 'pin':
      return (
        <svg {...props}>
          <path d="M12 21s-7-6.2-7-11a7 7 0 1 1 14 0c0 4.8-7 11-7 11Z" />
          <circle cx="12" cy="10" r="2.5" />
        </svg>
      );
    case 'scale':
      return (
        <svg {...props}>
          <path d="M12 3v18M5 7l-2 5a3.5 3.5 0 0 0 7 0L8 7M19 7l-2 5a3.5 3.5 0 0 0 7 0l-2-5M3 7h10M14 7h7" />
        </svg>
      );
    case 'message':
      return (
        <svg {...props}>
          <path d="M21 12a8 8 0 1 1-3.2-6.4L21 4l-1.2 4.4A8 8 0 0 1 21 12Z" />
        </svg>
      );
    case 'history':
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="9" />
          <path d="M12 7v5l3 3" />
        </svg>
      );
    case 'settings':
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3h0a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9v0a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.6 1Z" />
        </svg>
      );
    case 'logout':
      return (
        <svg {...props}>
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
          <path d="M16 17l5-5-5-5M21 12H9" />
        </svg>
      );
    case 'search':
      return (
        <svg {...props}>
          <circle cx="11" cy="11" r="7" />
          <path d="M21 21l-4.3-4.3" />
        </svg>
      );
    case 'chevronRight':
      return (
        <svg {...props}>
          <path d="M9 6l6 6-6 6" />
        </svg>
      );
    case 'chevronDown':
      return (
        <svg {...props}>
          <path d="M6 9l6 6 6-6" />
        </svg>
      );
    case 'download':
      return (
        <svg {...props}>
          <path d="M12 3v12m0 0l-4-4m4 4l4-4M5 21h14" />
        </svg>
      );
    case 'alert':
      return (
        <svg {...props}>
          <path d="M12 9v4M12 17h.01" />
          <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
        </svg>
      );
    case 'check':
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="9" />
          <path d="M8 12l2.5 2.5L16 9" />
        </svg>
      );
    case 'plus':
      return (
        <svg {...props}>
          <path d="M12 5v14M5 12h14" />
        </svg>
      );
    case 'grid':
      return (
        <svg {...props}>
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="7" rx="1" />
          <rect x="3" y="14" width="7" height="7" rx="1" />
          <rect x="14" y="14" width="7" height="7" rx="1" />
        </svg>
      );
    default:
      return null;
  }
}
