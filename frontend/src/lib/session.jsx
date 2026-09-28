import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { setEmployee } from './api.js'
import { load, remove, save } from './storage.js'

const Ctx = createContext(null)

export function SessionProvider({ children }) {
  const [employee, setEmp] = useState(() => load('nxr.employee', null))
  const [toast, setToast] = useState(null)

  useEffect(() => { setEmployee(employee?.employee_id || null) }, [employee])
  useEffect(() => {
    if (!toast) return undefined
    const t = setTimeout(() => setToast(null), 3200)
    return () => clearTimeout(t)
  }, [toast])

  const value = useMemo(() => ({
    employee,
    signIn: (e) => { setEmployee(e.employee_id); save('nxr.employee', e); setEmp(e) },
    signOut: () => { remove('nxr.employee'); setEmployee(null); setEmp(null) },
    notify: (msg) => setToast(msg),
    toast,
  }), [employee, toast])

  if (employee) setEmployee(employee.employee_id) // before the first child request
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export const useSession = () => useContext(Ctx)
