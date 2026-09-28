import { CalendarCheck, Coffee, HeartPulse, Sparkles, Sun } from 'lucide-react'

// Each leave type keeps its own colour and icon everywhere in the portal.
const LEAVE_STYLE = {
  EL: { c: 'c-indigo', Icon: Sun },
  CL: { c: 'c-sky', Icon: Coffee },
  SL: { c: 'c-rose', Icon: HeartPulse },
  RH: { c: 'c-amber', Icon: Sparkles },
}
const FALLBACK = ['c-violet', 'c-emerald']

export const leaveStyle = (code, i = 0) => LEAVE_STYLE[code] || { c: FALLBACK[i % FALLBACK.length], Icon: CalendarCheck }
