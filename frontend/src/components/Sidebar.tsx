/**
 * Sidebar.tsx — Barre de navigation latérale
 *
 * C'est le menu à gauche de l'application.
 * Chaque NavItem est un lien vers une page.
 */

import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Play,
  History,
  Settings,
  FolderKanban,
  BookOpen,
  Activity,
} from 'lucide-react'

// Définition des liens du menu
const navItems = [
  {
    section: 'Exécution',
    links: [
      { to: '/',          icon: LayoutDashboard, label: 'Tableau de bord' },
      { to: '/execute',   icon: Play,            label: 'Lancer' },
      { to: '/history',   icon: History,         label: 'Historique' },
    ],
  },
  {
    section: 'Projets',
    links: [
      { to: '/projects/awb',  icon: FolderKanban, label: 'AWB' },
      { to: '/projects/bmce', icon: FolderKanban, label: 'BMCE' },
      { to: '/projects/cdg',  icon: FolderKanban, label: 'CDG' },
    ],
  },
  {
    section: 'Outils',
    links: [
      { to: '/config',   icon: Settings,  label: 'Configuration' },
      { to: '/docs',     icon: BookOpen,  label: 'Documentation' },
    ],
  },
]

export default function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 h-screen w-60 bg-[#1a1d27] border-r border-[#2d3148] flex flex-col z-10">

      {/* Logo / Titre de l'app */}
      <div className="px-5 py-5 border-b border-[#2d3148]">
        <div className="flex items-center gap-2">
          <Activity className="text-indigo-500 w-5 h-5" />
          <span className="font-semibold text-white text-sm tracking-wide">Megara TNR</span>
        </div>
        <p className="text-[#64748b] text-xs mt-1">Plateforme d'automatisation</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 overflow-y-auto">
        {navItems.map((group) => (
          <div key={group.section} className="mb-5">

            {/* Titre de section */}
            <p className="text-[#475569] text-[10px] font-semibold uppercase tracking-widest px-2 mb-1">
              {group.section}
            </p>

            {/* Liens */}
            {group.links.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 px-2 py-2 rounded-md text-sm mb-0.5 transition-colors ${
                    isActive
                      ? 'bg-indigo-600/20 text-indigo-400 font-medium'
                      : 'text-[#94a3b8] hover:bg-[#252836] hover:text-white'
                  }`
                }
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                {label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* Pied de sidebar */}
      <div className="px-5 py-4 border-t border-[#2d3148]">
        <p className="text-[#475569] text-xs">v1.0.0</p>
      </div>
    </aside>
  )
}
