export const initials = (name = '') => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase()

export function fmtDate(iso, opts = { day: 'numeric', month: 'short', year: 'numeric' }) {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('en-IN', opts)
}

export function greeting(date = new Date()) {
  const h = date.getHours()
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'
}

export const shortDoc = (title = '') => title
  .replace('Policy on Prevention of Sexual Harassment (POSH)', 'POSH Policy')
  .replace(', Information Security and Acceptable Use Policy', ' & Security Policy')
  .replace('Attendance, Hybrid Work and Overtime Policy', 'Attendance & Hybrid Work')
  .replace('Travel and Expense Reimbursement Policy', 'Travel & Expense Policy')
  .replace('Compensation and Benefits Policy', 'Compensation & Benefits')
