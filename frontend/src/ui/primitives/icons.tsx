import type { JSX, SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement>

const base = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
} as const

export function SendIcon(props: IconProps): JSX.Element {
  return (
    <svg {...base} {...props} aria-hidden="true">
      <path d="M4.5 12h13M12.5 6.5 18.5 12l-6 5.5" />
    </svg>
  )
}

export function StopIcon(props: IconProps): JSX.Element {
  return (
    <svg {...base} {...props} aria-hidden="true">
      <rect x="7.5" y="7.5" width="9" height="9" rx="1.5" fill="currentColor" stroke="none" />
    </svg>
  )
}

export function NewChatIcon(props: IconProps): JSX.Element {
  return (
    <svg {...base} {...props} aria-hidden="true">
      <path d="M12 5v14M5 12h14" />
    </svg>
  )
}

export function ChevronIcon(props: IconProps): JSX.Element {
  return (
    <svg {...base} {...props} aria-hidden="true">
      <path d="m8.5 10.5 3.5 3.5 3.5-3.5" />
    </svg>
  )
}

export function ToolIcon(props: IconProps): JSX.Element {
  return (
    <svg {...base} {...props} aria-hidden="true">
      <path d="M14.2 6.3a3.6 3.6 0 0 0 4.6 4.6l-7.1 7.1a2 2 0 0 1-2.8 0l-1.7-1.7a2 2 0 0 1 0-2.8z" />
    </svg>
  )
}

export function SourceIcon(props: IconProps): JSX.Element {
  return (
    <svg {...base} {...props} aria-hidden="true">
      <path d="M6 4.5h8.5L18 8v11.5H6z" />
      <path d="M14 4.5V8h4M9 12.5h6M9 15.5h4" />
    </svg>
  )
}

export function AlertIcon(props: IconProps): JSX.Element {
  return (
    <svg {...base} {...props} aria-hidden="true">
      <path d="M12 4.5 20.5 19h-17z" />
      <path d="M12 10v4M12 16.5v.5" />
    </svg>
  )
}
