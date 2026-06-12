/**
 * ExecuteVars.tsx — Configuration des variables + lancement + monitoring
 *
 * Affiché sur /execute/:client/:module/:process
 *  1. Formulaire de variables éditables (chargé depuis le backend)
 *  2. Bouton "Lancer l'exécution"
 *  3. Logs en temps réel (WebSocket) après lancement
 *  4. Captures d'écran exportables dès la fin du process
 */

import { useEffect, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  ArrowLeft, Play, Save, Upload, CheckCircle, XCircle,
  Loader2, Download, Camera, ImageIcon, ChevronRight,
} from 'lucide-react'
import {
  getVariables, updateVariables, parseVariableFile, createExecution, getScreenshots,
  getScreenshotsDownloadUrl, getScreenshotUrl,
  type VariableEntry, type Execution, type LogEntry,
} from '../api/client'

export default function ExecuteVars() {
  const { client, module: mod, process } = useParams<{
    client: string; module: string; process: string
  }>()

  // ── Variables ──────────────────────────────────────────────────────────────
  const [editedVars, setEditedVars] = useState<VariableEntry[]>([])
  const [saving,     setSaving]     = useState(false)
  const [savedOk,    setSavedOk]    = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data: varsData, isLoading: varsLoading, error: varsError } = useQuery({
    queryKey: ['variables', client, process],
    queryFn:  () => getVariables(client!, process!),
    retry: false,
  })

  useEffect(() => {
    if (varsData) setEditedVars(varsData.variables)
  }, [varsData])

  function updateVar(idx: number, value: string) {
    setEditedVars(prev => prev.map((v, i) => i === idx ? { ...v, value } : v))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await updateVariables(client!, process!, editedVars)
      setSavedOk(true)
      setTimeout(() => setSavedOk(false), 2500)
    } finally {
      setSaving(false)
    }
  }

  function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = ev => {
      const parsed = parseVariableFile(ev.target?.result as string)
      if (parsed.length > 0) setEditedVars(parsed)
    }
    reader.readAsText(file, 'utf-8')
    e.target.value = ''
  }

  // ── Execution + logs ───────────────────────────────────────────────────────
  const [execution,  setExecution]  = useState<Execution | null>(null)
  const [logs,       setLogs]       = useState<LogEntry[]>([])
  const [wsStatus,   setWsStatus]   = useState<'idle' | 'connecting' | 'connected' | 'closed'>('idle')
  const wsRef    = useRef<WebSocket | null>(null)
  const logsEnd  = useRef<HTMLDivElement>(null)

  useEffect(() => {
    logsEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  function startWs(execId: number) {
    wsRef.current?.close()
    setWsStatus('connecting')
    const ws = new WebSocket(`ws://localhost:8000/ws/executions/${execId}/logs`)
    wsRef.current = ws
    ws.onopen  = () => setWsStatus('connected')
    ws.onerror = () => setWsStatus('closed')
    ws.onclose = () => setWsStatus('closed')
    ws.onmessage = e => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'log') {
        setLogs(prev => [...prev, {
          id:        Date.now() + Math.random(),
          level:     msg.level,
          message:   msg.message,
          timestamp: msg.timestamp,
        }])
      } else if (msg.type === 'done') {
        setWsStatus('closed')
        setExecution(prev => prev ? { ...prev, status: msg.status as Execution['status'] } : null)
      }
    }
  }

  useEffect(() => () => wsRef.current?.close(), [])

  const launchMutation = useMutation({
    mutationFn: createExecution,
    onSuccess: exec => {
      setExecution(exec)
      setLogs([])
      startWs(exec.id)
    },
  })

  async function handleLaunch() {
    if (!client || !mod || !process) return
    // Save variables first if there are any
    if (editedVars.length > 0 && !varsError) {
      await updateVariables(client, process, editedVars)
    }
    launchMutation.mutate({ client, module: mod, process })
  }

  // ── Screenshots ────────────────────────────────────────────────────────────
  const isDone = execution?.status === 'success' || execution?.status === 'error'

  const { data: screenshots } = useQuery({
    queryKey:      ['screenshots', execution?.id],
    queryFn:       () => getScreenshots(execution!.id),
    enabled:       !!execution && isDone,
    refetchInterval: q => (!q.state.data || q.state.data.count === 0 ? 3000 : false),
    retry: 2,
  })
  const [showGallery, setShowGallery] = useState(false)

  // ── Colors ─────────────────────────────────────────────────────────────────
  const logColor = { INFO: 'text-slate-300', WARNING: 'text-yellow-400', ERROR: 'text-red-400' }

  const execId = execution?.id
  const isRunning = execution?.status === 'running' || execution?.status === 'pending'

  return (
    <div className="p-8 w-full max-w-4xl">

      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Link to="/execute" className="text-[#64748b] hover:text-white transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex items-center gap-2 text-sm">
          <span className="px-2 py-1 bg-[#2d3148] text-white rounded">{client?.toUpperCase()}</span>
          <ChevronRight className="w-4 h-4 text-[#475569]" />
          <span className="px-2 py-1 bg-[#2d3148] text-white rounded">{mod}</span>
          <ChevronRight className="w-4 h-4 text-[#475569]" />
          <span className="px-2 py-1 bg-indigo-600/30 border border-indigo-500/30 text-indigo-300 rounded">{process}</span>
        </div>
      </div>

      {/* ── Variables section ──────────────────────────────────────────────── */}
      <div className="mb-6 bg-[#1a1d27] border border-[#2d3148] rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-[#2d3148] flex items-center justify-between">
          <h2 className="text-white font-medium text-sm">Variables de saisie</h2>
          <div className="flex items-center gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt"
              className="hidden"
              onChange={handleImport}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#252836] hover:bg-[#2d3148] text-[#94a3b8] hover:text-white text-xs transition-colors"
            >
              <Upload className="w-3.5 h-3.5" />
              Importer .txt
            </button>
            {editedVars.length > 0 && !varsError && (
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#252836] hover:bg-[#2d3148] text-[#94a3b8] hover:text-white text-xs transition-colors disabled:opacity-50"
              >
                {saving
                  ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  : savedOk
                    ? <CheckCircle className="w-3.5 h-3.5 text-green-400" />
                    : <Save className="w-3.5 h-3.5" />
                }
                {savedOk ? 'Sauvegardé !' : 'Sauvegarder'}
              </button>
            )}
          </div>
        </div>

        {varsLoading && (
          <div className="px-5 py-6 flex items-center gap-2 text-[#64748b] text-sm">
            <Loader2 className="w-4 h-4 animate-spin" />
            Chargement des variables...
          </div>
        )}

        {varsError && editedVars.length === 0 && (
          <div className="px-5 py-4 text-[#64748b] text-sm italic">
            Pas de fichier de variables configuré — importez un .txt pour remplir les variables.
          </div>
        )}

        {!varsLoading && editedVars.length > 0 && (
          <div className="divide-y divide-[#2d3148]">
            {editedVars.map((v, i) => (
              <div key={v.key} className="flex items-center px-5 py-2.5 gap-4">
                <label className="w-64 flex-shrink-0 text-xs text-[#94a3b8] font-mono">
                  {v.key}
                  {v.required && <span className="text-indigo-400 ml-0.5">*</span>}
                </label>
                <input
                  type="text"
                  value={v.value}
                  onChange={e => updateVar(i, e.target.value)}
                  className="flex-1 bg-[#0f1117] border border-[#2d3148] rounded-lg px-3 py-1.5 text-sm text-white font-mono focus:outline-none focus:border-indigo-500 transition-colors"
                />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Launch button ──────────────────────────────────────────────────── */}
      <button
        onClick={handleLaunch}
        disabled={launchMutation.isPending || isRunning}
        className="flex items-center gap-2 px-6 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl font-medium text-sm transition-colors mb-6"
      >
        {launchMutation.isPending || isRunning
          ? <><Loader2 className="w-4 h-4 animate-spin" />Lancement en cours...</>
          : <><Play className="w-4 h-4" />Lancer l'exécution</>
        }
      </button>

      {launchMutation.isError && (
        <p className="mb-4 text-red-400 text-sm">
          Erreur : {(launchMutation.error as any)?.response?.data?.detail || 'Erreur inconnue'}
        </p>
      )}

      {/* ── Logs ──────────────────────────────────────────────────────────── */}
      {execution && (
        <div className="mb-4 bg-[#0d0f16] border border-[#2d3148] rounded-xl overflow-hidden">
          <div className="px-4 py-2 border-b border-[#2d3148] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${wsStatus === 'connected' ? 'bg-green-500 animate-pulse' : 'bg-slate-500'}`} />
              <span className="text-[#64748b] text-xs font-mono">
                {wsStatus === 'connected' ? 'Connecté — logs en direct' :
                 wsStatus === 'connecting' ? 'Connexion...' : 'Terminé'}
              </span>
              {execution.status === 'success' && (
                <span className="flex items-center gap-1 text-green-400 text-xs"><CheckCircle className="w-3 h-3" /> Succès</span>
              )}
              {execution.status === 'error' && (
                <span className="flex items-center gap-1 text-red-400 text-xs"><XCircle className="w-3 h-3" /> Erreur</span>
              )}
            </div>
            <span className="text-[#475569] text-xs">#{execId} · {logs.length} lignes</span>
          </div>
          <div className="overflow-y-auto max-h-96 p-4 font-mono text-xs">
            {logs.length === 0 && (
              <div className="text-[#475569] flex items-center gap-2">
                <Loader2 className="w-3 h-3 animate-spin" />En attente des logs...
              </div>
            )}
            {logs.map((log, idx) => (
              <div key={idx} className="flex gap-3 mb-0.5 leading-5">
                <span className="text-[#475569] flex-shrink-0 w-20">
                  {new Date(log.timestamp).toLocaleTimeString('fr-FR')}
                </span>
                <span className={`flex-shrink-0 w-16 ${logColor[log.level as keyof typeof logColor] || 'text-slate-300'}`}>
                  [{log.level}]
                </span>
                <span className={logColor[log.level as keyof typeof logColor] || 'text-slate-300'}>
                  {log.message}
                </span>
              </div>
            ))}
            <div ref={logsEnd} />
          </div>
        </div>
      )}

      {/* ── Screenshots ────────────────────────────────────────────────────── */}
      {isDone && execId && (
        <div className="bg-[#1a1d27] border border-[#2d3148] rounded-xl overflow-hidden">
          <div className="px-5 py-3 flex items-center justify-between border-b border-[#2d3148]">
            <div className="flex items-center gap-2">
              <Camera className="w-4 h-4 text-indigo-400" />
              <span className="text-white text-sm font-medium">Captures d'écran</span>
              {screenshots && (
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  screenshots.count > 0
                    ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                    : 'bg-slate-500/10 text-slate-400 border border-slate-500/20'
                }`}>
                  {screenshots.count} fichier{screenshots.count !== 1 ? 's' : ''}
                </span>
              )}
            </div>
            {screenshots && screenshots.count > 0 && (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowGallery(v => !v)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#252836] hover:bg-[#2d3148] text-[#94a3b8] hover:text-white text-xs transition-colors"
                >
                  <ImageIcon className="w-3.5 h-3.5" />
                  {showGallery ? 'Masquer' : 'Aperçu'}
                </button>
                <a
                  href={getScreenshotsDownloadUrl(execId)}
                  download
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  Télécharger ZIP
                </a>
              </div>
            )}
          </div>

          {(!screenshots || screenshots.count === 0) && (
            <div className="px-5 py-4 text-[#64748b] text-sm">
              {screenshots ? 'Aucune capture — le script n\'a pas détecté d\'erreurs.' : 'Chargement...'}
            </div>
          )}

          {screenshots && screenshots.count > 0 && showGallery && (
            <div className="p-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {screenshots.files.map(file => (
                <a
                  key={file.path}
                  href={getScreenshotUrl(execId, file.path)}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={file.path}
                  className="group block rounded-lg overflow-hidden border border-[#2d3148] hover:border-indigo-500 transition-colors"
                >
                  <img
                    src={getScreenshotUrl(execId, file.path)}
                    alt={file.name}
                    className="w-full h-24 object-cover object-top bg-[#0d0f16]"
                    loading="lazy"
                  />
                  <div className="px-2 py-1 bg-[#141720]">
                    <p className="text-[10px] text-[#64748b] truncate group-hover:text-white transition-colors">
                      {file.name.replace(/\.[^.]+$/, '')}
                    </p>
                  </div>
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
