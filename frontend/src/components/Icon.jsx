import React from 'react'

const P = {
  dashboard: 'M4 4h7v7H4zM13 4h7v5h-7zM13 12h7v8h-7zM4 15h7v5H4z',
  library: 'm12 3 9 5-9 5-9-5 9-5zM3 12l9 5 9-5M3 16l9 5 9-5',
  decision: 'M3 17l6-6 4 4 8-8M15 7h6v6',
  training: 'm22 10-10-5L2 10l10 5 10-5zM6 12v5c0 1.3 3 3 6 3s6-1.7 6-3v-5',
  twin: 'm12 2 9 5v10l-9 5-9-5V7zM12 22V12M21 7l-9 5-9-5',
  reports: 'M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9zM14 3v6h6M8 13h8M8 17h6',
  warroom: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20M2 12h20M12 2c2.5 3 2.5 17 0 20M12 2c-2.5 3-2.5 17 0 20',
  compose: 'M7 4v5a3 3 0 0 0 3 3h4M17 4v5a3 3 0 0 1-3 3h-1M12 12v8M9 17l3 3 3-3',
  builder: 'M6 3a3 3 0 1 0 0 6 3 3 0 0 0 0-6M6 9v6M6 15a3 3 0 1 0 0 6 3 3 0 0 0 0-6M18 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6M18 6h-4a5 5 0 0 0-5 5v4',
  simulation: 'M2 12h4l3-8 4 16 3-8h6',
  data: 'M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3',
  assumptions: 'M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6',
}

export default function Icon({ name, size = 18 }) {
  return (
    <svg className="nav-ic" width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d={P[name] || ''} />
    </svg>
  )
}
