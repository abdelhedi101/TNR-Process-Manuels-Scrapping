/**
 * History.tsx — Historique de toutes les exécutions
 */

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getExecutions, type Execution } from '../api/client'

function StatusBadge({ status }: { status: Execution['status'] }) {
  const styles = {
    pending:  'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    running:  'bg-blue-500/10 text-blue-400 border-blue-500/20',
    success:  'bg-green-500/10 text-green-400 border-green-500/20',
    error:    'bg-red-500/10 text-red-400 border-red-500/20',
    stopped:  'bg-slate-500/10 text-slate-400 border-slate-500/20',
  }
  const labels = { pending: 'En attente', running: 'En cours', success: 'Succès', error: 'Erreur', stopped: 'Arrêté' }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium border ${styles[status]}`}>
      {labels[status]}
    </span>
  )
}

function duration(start: string, end: string | null) {
  if (!end) return '—'
  const ms = new Date(end).getTime() - new Date(start).getTime()
  const s = Math.round(ms / 1000)
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`
}

export default function History() {
  const { data: executions = [], isLoading } = useQuery({
    queryKey: ['executions'],
    queryFn: () => getExecutions({ limit: 100 }),
    refetchInterval: 10000,
  })

  return (
    <div className="p-8 w-full">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-white">Historique</h1>
          <p className="text-[#64748b] text-sm mt-1">{executions.length} exécution(s) au total</p>
        </div>
        <Link
          to="/execute"
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg font-medium transition-colors"
        >
          + Nouvelle exécution
        </Link>
      </div>

      <div className="bg-[#1a1d27] border border-[#2d3148] rounded-xl overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-[#64748b]">Chargement...</div>
        ) : executions.length === 0 ? (
          <div className="p-12 text-center text-[#64748b]">Aucune exécution pour l'instant.</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="text-[#475569] text-xs uppercase tracking-wide bg-[#141720]">
                <th className="px-5 py-3 text-left">ID</th>
                <th className="px-5 py-3 text-left">Client</th>
                <th className="px-5 py-3 text-left">Module</th>
                <th className="px-5 py-3 text-left">Processus</th>
                <th className="px-5 py-3 text-left">Statut</th>
                <th className="px-5 py-3 text-left">Durée</th>
                <th className="px-5 py-3 text-left">Démarré le</th>
                <th className="px-5 py-3 text-left"></th>
              </tr>
            </thead>
            <tbody>
              {executions.map((exec) => (
                <tr key={exec.id} className="border-t border-[#1e2130] hover:bg-[#1e2130] transition-colors">
                  <td className="px-5 py-3 text-[#475569] text-sm font-mono">#{exec.id}</td>
                  <td className="px-5 py-3 text-white text-sm font-semibold uppercase">{exec.client}</td>
                  <td className="px-5 py-3 text-[#94a3b8] text-sm">{exec.module}</td>
                  <td className="px-5 py-3 text-[#94a3b8] text-sm">{exec.process}</td>
                  <td className="px-5 py-3"><StatusBadge status={exec.status} /></td>
                  <td className="px-5 py-3 text-[#64748b] text-sm font-mono">{duration(exec.started_at, exec.ended_at)}</td>
                  <td className="px-5 py-3 text-[#64748b] text-xs">
                    {new Date(exec.started_at).toLocaleString('fr-FR')}
                  </td>
                  <td className="px-5 py-3">
                    <Link to={`/monitor/${exec.id}`} className="text-indigo-400 hover:text-indigo-300 text-xs">
                      Logs →
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
