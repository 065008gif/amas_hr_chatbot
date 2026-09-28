import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { BarChart3, BookOpenText, Home, Info, LogOut, Menu, MessageSquareText, Ticket, X } from 'lucide-react'
import { useSession } from '../lib/session.jsx'
import { initials } from '../lib/format.js'

const NAV = [
  { to: '/', label: 'Home', Icon: Home, end: true },
  { to: '/chat', label: 'Ask Nia', Icon: MessageSquareText, tag: 'AI' },
  { to: '/tickets', label: 'My Tickets', Icon: Ticket },
  { to: '/library', label: 'Policy Library', Icon: BookOpenText },
]
const ADMIN = [{ to: '/insights', label: 'HR Insights', Icon: BarChart3, tag: 'Demo' }]
const TITLES = { '/': 'Home', '/chat': 'Ask Nia', '/tickets': 'My Tickets', '/library': 'Policy Library', '/insights': 'HR Insights', '/about': 'About' }

export default function Layout() {
  const { employee, signOut } = useSession()
  const [open, setOpen] = useState(false)
  const loc = useLocation()
  useEffect(() => { setOpen(false) }, [loc.pathname])
  const title = TITLES[loc.pathname] || (loc.pathname.startsWith('/library') ? 'Policy Library' : 'Nexora People Portal')

  const link = ({ to, label, Icon, end, tag }) => (
    <NavLink key={to} to={to} end={end}>
      <Icon size={18} aria-hidden="true" />{label}
      {tag && <span className={`badge tag ${tag === 'AI' ? 'brand' : 'outline'}`}>{tag}</span>}
    </NavLink>
  )

  return (
    <div className="shell">
      {open && <div className="drawer-backdrop" onClick={() => setOpen(false)} aria-hidden="true" />}
      <aside className={`sidebar ${open ? 'open' : ''}`} aria-label="Main navigation">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">N</div>
          <div>
            <div className="brand-name">Nexora</div>
            <div className="brand-sub">People Portal</div>
          </div>
          <button className="btn btn-ghost icon-btn menu-btn" style={{ marginLeft: 'auto' }} onClick={() => setOpen(false)} aria-label="Close menu"><X size={18} /></button>
        </div>
        <nav className="nav">
          {NAV.map(link)}
          <div className="nav-label">Admin</div>
          {ADMIN.map(link)}
          <div className="nav-label">Help</div>
          {link({ to: '/about', label: 'About & privacy', Icon: Info })}
        </nav>
        <div className="sidebar-foot">
          AI assistant, not HR advice. Fictional company and documents; demo employee data.
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <button className="btn btn-ghost icon-btn menu-btn" onClick={() => setOpen(true)} aria-label="Open menu"><Menu size={20} /></button>
          <h1>{title}</h1>
          <div className="spacer" />
          <div className="user-chip" title={`${employee.name}, ${employee.designation} (demo account)`}>
            <div className="avatar" aria-hidden="true">{initials(employee.name)}</div>
            <div className="who"><b>{employee.name}</b><span>{employee.grade} · {employee.location}</span></div>
            <button className="btn btn-ghost icon-btn" onClick={signOut} aria-label="Switch demo employee" title="Switch demo employee"><LogOut size={16} /></button>
          </div>
        </header>
        <Outlet />
      </div>
    </div>
  )
}
