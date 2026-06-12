/**
 * Dashboard.tsx — Page d'accueil (tableau de bord)
 *
 * Affiche :
 * - Les statistiques globales (nombre d'exécutions, taux de succès)
 * - Les dernières exécutions
 * - Un bouton pour lancer une nouvelle exécution
 */

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Play, CheckCircle, XCircle, Clock, RefreshCw } from 'lucide-react'
import { getExecutions, type Execution } from '../api/client'

// Badge de statut coloré selon l'état de l'exécution
function StatusBadge({ status }: { status: Execution['status'] }) {
  const styles = {
    pending:  'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20',
    running:  'bg-blue-500/10 text-blue-400 border border-blue-500/20',
    success:  'bg-green-500/10 text-green-400 border border-green-500/20',
    error:    'bg-red-500/10 text-red-400 border border-red-500/20',
    stopped:  'bg-slate-500/10 text-slate-400 border border-slate-500/20',
  }
  const labels = {
    pending: 'En attente',
    running: 'En cours',
    success: 'Succès',
    error:   'Erreur',
    stopped: 'Arrêté',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${styles[status]}`}>
      {labels[status]}
    </span>
  )
}

// Formate une date ISO en "11/06/2026 14:32"
function formatDate(iso: string) {
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function Dashboard() {
  // useQuery : charge les données depuis le backend et les met en cache
  const { data: executions = [], isLoading, refetch } = useQuery({
    queryKey: ['executions'],
    queryFn: () => getExecutions({ limit: 20 }),
    refetchInterval: 10000, // recharge automatiquement toutes les 10 secondes
  })

  // Calcul des statistiques
  const total    = executions.length
  const success  = executions.filter(e => e.status === 'success').length
  const errors   = executions.filter(e => e.status === 'error').length
  const running  = executions.filter(e => e.status === 'running').length

  const stats = [
    { label: 'Total exécutions',  value: total,   icon: Clock,       color: 'text-slate-400'  },
    { label: 'Succès',            value: success,  icon: CheckCircle, color: 'text-green-400'  },
    { label: 'Erreurs',           value: errors,   icon: XCircle,     color: 'text-red-400'    },
    { label: 'En cours',          value: running,  icon: Play,        color: 'text-blue-400'   },
  ]

  return (
    <div className="p-8 max-w-6xl">

      {/* En-tête */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-white">Tableau de bord</h1>
          <p className="text-[#64748b] text-sm mt-1">Vue d'ensemble des exécutions TNR</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#1e2130] border border-[#2d3148] text-[#94a3b8] hover:text-white text-sm transition-colors"
          >
            <RefreshCw className="w-4 h-4" /> Actualiser
          </button>
          <Link
            to="/execute"
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors"
          >
            <Play className="w-4 h-4" /> Nouvelle exécution
          </Link>
        </div>
      </div>

      {/* Cartes de statistiques */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {stats.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-[#1a1d27] border border-[#2d3148] rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <p className="text-[#64748b] text-sm">{label}</p>
              <Icon className={`w-5 h-5 ${color}`} />
            </div>
            <p className="text-3xl font-bold text-white">{value}</p>
          </div>
        ))}
      </div>

      {/* Dernières exécutions */}
      <div className="bg-[#1a1d27] border border-[#2d3148] rounded-xl">
        <div className="px-6 py-4 border-b border-[#2d3148]">
          <h2 className="text-white font-medium">Dernières exécutions</h2>
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-[#64748b]">Chargement...</div>
        ) : executions.length === 0 ? (
          <div className="p-8 text-center text-[#64748b]">
            <p>Aucune exécution pour l'instant.</p>
            <Link to="/execute" className="text-indigo-400 hover:underline mt-2 inline-block text-sm">
              Lancer votre première exécution →
            </Link>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="text-[#475569] text-xs uppercase tracking-wide border-b border-[#2d3148]">
                <th className="px-6 py-3 text-left">#</th>
                <th className="px-6 py-3 text-left">Client</th>
                <th className="px-6 py-3 text-left">Module</th>
                <th className="px-6 py-3 text-left">Processus</th>
                <th className="px-6 py-3 text-left">Statut</th>
                <th className="px-6 py-3 text-left">Démarré</th>
                <th className="px-6 py-3 text-left">Action</th>
              </tr>
            </thead>
            <tbody>
              {executions.map((exec) => (
                <tr key={exec.id} className="border-b border-[#1e2130] hover:bg-[#1e2130] transition-colors">
                  <td className="px-6 py-3 text-[#64748b] text-sm">#{exec.id}</td>
                  <td className="px-6 py-3 text-white text-sm font-medium uppercase">{exec.client}</td>
                  <td className="px-6 py-3 text-[#94a3b8] text-sm">{exec.module}</td>
                  <td className="px-6 py-3 text-[#94a3b8] text-sm">{exec.process}</td>
                  <td className="px-6 py-3"><StatusBadge status={exec.status} /></td>
                  <td className="px-6 py-3 text-[#64748b] text-xs">{formatDate(exec.started_at)}</td>
                  <td className="px-6 py-3">
                    <Link
                      to={`/monitor/${exec.id}`}
                      className="text-indigo-400 hover:text-indigo-300 text-xs hover:underline"
                    >
                      Voir les logs →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
