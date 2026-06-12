/**
 * Monitor.tsx — Page de suivi en temps réel d'une exécution
 *
 * Ce que tu vois ici :
 * - Le statut de l'exécution (en cours / succès / erreur)
 * - Les logs qui défilent en temps réel via WebSocket
 * - Un bouton Stop pour arrêter l'exécution
 */

import { useEffect, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Square, CheckCircle, XCircle, Loader2 } from 'lucide-react'
import { getExecution, stopExecution, type LogEntry } from '../api/client'

export default function Monitor() {
  // useParams récupère l'id depuis l'URL : /monitor/42 → id = "42"
  const { id } = useParams<{ id: string }>()
  const executionId = Number(id)
  const queryClient = useQueryClient()

  // Liste des logs affichés à l'écran
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [wsStatus, setWsStatus] = useState<'connecting' | 'connected' | 'closed'>('connecting')

  // Référence vers le bas de la liste de logs (pour l'auto-scroll)
  const logsEndRef = useRef<HTMLDivElement>(null)

  // Charger les infos de l'exécution
  const { data: execution, refetch } = useQuery({
    queryKey: ['execution', executionId],
    queryFn: () => getExecution(executionId),
    refetchInterval: (query) => {
      const s = query.state.data?.status
      return s === 'running' || s === 'pending' ? 3000 : false
    },
  })

  // Mutation pour arrêter l'exécution
  const stopMutation = useMutation({
    mutationFn: () => stopExecution(executionId),
    onSuccess: () => refetch(),
  })

  // Connexion WebSocket — logs en temps réel
  useEffect(() => {
    const wsUrl = `ws://localhost:8000/ws/executions/${executionId}/logs`
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => setWsStatus('connected')

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)

      if (msg.type === 'log') {
        // Nouveau log reçu → l'ajouter à la liste
        setLogs(prev => [...prev, {
          id:        Date.now(),
          level:     msg.level,
          message:   msg.message,
          timestamp: msg.timestamp,
        }])
      } else if (msg.type === 'done') {
        // Exécution terminée → rafraîchir les infos
        setWsStatus('closed')
        queryClient.invalidateQueries({ queryKey: ['execution', executionId] })
        queryClient.invalidateQueries({ queryKey: ['executions'] })
      }
    }

    ws.onerror = () => setWsStatus('closed')
    ws.onclose = () => setWsStatus('closed')

    // Fermer la connexion quand on quitte la page
    return () => ws.close()
  }, [executionId])

  // Auto-scroll vers le bas à chaque nouveau log
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  // Couleur des lignes de log selon le niveau
  const logColors = {
    INFO:    'text-slate-300',
    WARNING: 'text-yellow-400',
    ERROR:   'text-red-400',
  }

  return (
    <div className="p-8 h-screen flex flex-col max-w-5xl">

      {/* En-tête */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Link to="/history" className="text-[#64748b] hover:text-white transition-colors">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold text-white">
                Exécution #{executionId}
              </h1>
              {execution && (
                <StatusIcon status={execution.status} />
              )}
            </div>
            {execution && (
              <p className="text-[#64748b] text-sm mt-0.5">
                {execution.client.toUpperCase()} · {execution.module} · {execution.process}
              </p>
            )}
          </div>
        </div>

        {/* Bouton Stop */}
        {execution?.status === 'running' && (
          <button
            onClick={() => stopMutation.mutate()}
            disabled={stopMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-red-600/20 hover:bg-red-600/30 border border-red-500/30 text-red-400 rounded-lg text-sm transition-colors"
          >
            <Square className="w-4 h-4" />
            Arrêter
          </button>
        )}
      </div>

      {/* Panneau de logs */}
      <div className="flex-1 bg-[#0d0f16] border border-[#2d3148] rounded-xl overflow-hidden flex flex-col">

        {/* Barre de statut des logs */}
        <div className="px-4 py-2 border-b border-[#2d3148] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${wsStatus === 'connected' ? 'bg-green-500 animate-pulse' : 'bg-slate-500'}`} />
            <span className="text-[#64748b] text-xs font-mono">
              {wsStatus === 'connected' ? 'Connecté — logs en direct' :
               wsStatus === 'connecting' ? 'Connexion...' : 'Terminé'}
            </span>
          </div>
          <span className="text-[#475569] text-xs">{logs.length} lignes</span>
        </div>

        {/* Zone de logs — défile automatiquement */}
        <div className="flex-1 overflow-y-auto p-4 font-mono text-xs">
          {logs.length === 0 ? (
            <div className="text-[#475569] flex items-center gap-2">
              <Loader2 className="w-3 h-3 animate-spin" />
              En attente des logs...
            </div>
          ) : (
            logs.map((log, index) => (
              <div key={index} className="flex gap-3 mb-0.5 leading-5">
                {/* Timestamp */}
                <span className="text-[#475569] flex-shrink-0 w-20">
                  {new Date(log.timestamp).toLocaleTimeString('fr-FR')}
                </span>
                {/* Niveau */}
                <span className={`flex-shrink-0 w-16 ${logColors[log.level as keyof typeof logColors] || 'text-slate-300'}`}>
                  [{log.level}]
                </span>
                {/* Message */}
                <span className={logColors[log.level as keyof typeof logColors] || 'text-slate-300'}>
                  {log.message}
                </span>
              </div>
            ))
          )}
          {/* Ancre pour l'auto-scroll */}
          <div ref={logsEndRef} />
        </div>
      </div>

      {/* Message de fin */}
      {execution?.status === 'success' && (
        <div className="mt-4 p-4 bg-green-500/10 border border-green-500/20 rounded-xl flex items-center gap-3">
          <CheckCircle className="w-5 h-5 text-green-400" />
          <p className="text-green-400 text-sm font-medium">Exécution terminée avec succès</p>
        </div>
      )}
      {execution?.status === 'error' && (
        <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3">
          <XCircle className="w-5 h-5 text-red-400" />
          <p className="text-red-400 text-sm">{execution.error_msg || 'Erreur lors de l\'exécution'}</p>
        </div>
      )}
    </div>
  )
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'running')  return <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
  if (status === 'success')  return <CheckCircle className="w-4 h-4 text-green-400" />
  if (status === 'error')    return <XCircle className="w-4 h-4 text-red-400" />
  return null
}
