/**
 * Phase 8 Dashboard -- inline SVG icon strings (stroke uses currentColor
 * so icons inherit whatever text color their container sets).
 */
const stroke = 'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"';

export const icons = {
  home: `<svg viewBox="0 0 24 24" ${stroke}><path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/></svg>`,
  chart: `<svg viewBox="0 0 24 24" ${stroke}><path d="M4 20V10M12 20V4M20 20v-7"/></svg>`,
  file: `<svg viewBox="0 0 24 24" ${stroke}><path d="M6 2h9l5 5v15H6z"/><path d="M14 2v6h6"/></svg>`,
  users: `<svg viewBox="0 0 24 24" ${stroke}><circle cx="9" cy="8" r="3.2"/><path d="M2.5 20a6.5 6.5 0 0113 0"/><path d="M16 4.5a3.2 3.2 0 010 6.4"/><path d="M15 13.5a6.5 6.5 0 016.5 6.5"/></svg>`,
  bell: `<svg viewBox="0 0 24 24" ${stroke}><path d="M18 16v-5a6 6 0 10-12 0v5l-2 3h16z"/><path d="M9.5 20a2.5 2.5 0 005 0"/></svg>`,
  settings: `<svg viewBox="0 0 24 24" ${stroke}><circle cx="12" cy="12" r="3.2"/><path d="M19 12a7 7 0 00-.14-1.4l2-1.55-2-3.46-2.36.95a7 7 0 00-2.4-1.4L13.6 2h-3.2l-.5 2.14a7 7 0 00-2.4 1.4l-2.36-.95-2 3.46 2 1.55A7 7 0 005 12c0 .47.05.93.14 1.4l-2 1.55 2 3.46 2.36-.95a7 7 0 002.4 1.4l.5 2.14h3.2l.5-2.14a7 7 0 002.4-1.4l2.36.95 2-3.46-2-1.55c.09-.47.14-.93.14-1.4z"/></svg>`,
  camera: `<svg viewBox="0 0 24 24" ${stroke}><path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13.5" r="3.5"/></svg>`,
  phone: `<svg viewBox="0 0 24 24" ${stroke}><rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/></svg>`,
  alert: `<svg viewBox="0 0 24 24" ${stroke}><path d="M12 3l10 18H2z"/><path d="M12 10v4"/><path d="M12 17h.01"/></svg>`,
  sun: `<svg viewBox="0 0 24 24" ${stroke}><circle cx="12" cy="12" r="4.2"/><path d="M12 2v2M12 20v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2 12h2M20 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"/></svg>`,
  moon: `<svg viewBox="0 0 24 24" ${stroke}><path d="M20 14.5A8.5 8.5 0 119.5 4a7 7 0 0010.5 10.5z"/></svg>`,
  eye: `<svg viewBox="0 0 24 24" ${stroke}><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>`,
  fps: `<svg viewBox="0 0 24 24" ${stroke}><path d="M4 4l16 16M4 20L20 4"/></svg>`,
  spark: `<svg viewBox="0 0 24 24" ${stroke}><path d="M12 2l1.8 5.6L19 9l-5.2 1.4L12 16l-1.8-5.6L5 9l5.2-1.4z"/></svg>`,
  check: `<svg viewBox="0 0 24 24" ${stroke}><path d="M20 6L9 17l-5-5"/></svg>`,
  refresh: `<svg viewBox="0 0 24 24" ${stroke}><path d="M21 12a9 9 0 10-3 6.7"/><path d="M21 5v6h-6"/></svg>`,
};
