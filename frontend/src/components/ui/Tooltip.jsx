/**
 * components/ui/Tooltip.jsx
 * Simple hover tooltip using CSS positioning.
 */

import { useState } from 'react'

export default function Tooltip({ children, content, position = 'top', className = '' }) {
  const [visible, setVisible] = useState(false)

  const positionStyles = {
    top:    'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full  left-1/2 -translate-x-1/2 mt-2',
    left:   'right-full top-1/2 -translate-y-1/2 mr-2',
    right:  'left-full  top-1/2 -translate-y-1/2 ml-2',
  }

  return (
    <span
      className={`relative inline-flex ${className}`}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      {children}
      {visible && content && (
        <span
          className={`
            absolute z-50 whitespace-nowrap px-2.5 py-1.5 rounded-md text-xs
            text-text-primary font-medium pointer-events-none
            ${positionStyles[position]}
          `}
          style={{
            background: 'rgba(15,20,38,0.95)',
            border: '1px solid rgba(79,70,229,0.3)',
            backdropFilter: 'blur(8px)',
            boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
          }}
        >
          {content}
        </span>
      )}
    </span>
  )
}
