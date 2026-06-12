/**
 * client.ts — Configuration centrale des appels HTTP vers le backend
 *
 * On utilise axios : une librairie qui simplifie les appels HTTP.
 * Toute l'application passe par ce fichier pour parler au backend.
 */

import axios from 'axios'

// Instance axios configurée avec l'URL de base du backend
// Grâce au proxy Vite, /api sera redirigé vers http://localhost:8000/api
const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

export default api


// ---------------------------------------------------------------------------
// Types TypeScript — définissent la forme des données
// (TypeScript vérifie au moment du développement qu'on ne fait pas d'erreurs)
// ---------------------------------------------------------------------------

export interface Client {
  slug: string
  name: string
  full_name: string
  auth_type: string
}

export interface Module {
  slug: string
  name: string
  port: number
  url: string
}

export interface ProcessType {
  slug: string
  name: string
  description: string
}

export interface Execution {
  id: number
  client: string
  module: string
  process: string
  status: 'pending' | 'running' | 'success' | 'error' | 'stopped'
  started_at: string
  ended_at: string | null
  error_msg: string | null
}

export interface LogEntry {
  id: number
  level: 'INFO' | 'WARNING' | 'ERROR'
  message: string
  timestamp: string
}

export interface ExecutionCreate {
  client: string
  module: string
  process: string
}


// ---------------------------------------------------------------------------
// Fonctions API — une fonction par endpoint backend
// ---------------------------------------------------------------------------

/** Récupère la liste des clients (AWB, BMCE, CDG) */
export const getClients = () =>
  api.get<Client[]>('/clients/').then(r => r.data)

/** Récupère les modules d'un client */
export const getModules = (clientSlug: string) =>
  api.get<Module[]>(`/clients/${clientSlug}/modules`).then(r => r.data)

/** Récupère les types de processus d'un client */
export const getProcesses = (clientSlug: string) =>
  api.get<ProcessType[]>(`/clients/${clientSlug}/processes`).then(r => r.data)

/** Lance une nouvelle exécution */
export const createExecution = (data: ExecutionCreate) =>
  api.post<Execution>('/executions', data).then(r => r.data)

/** Récupère l'historique des exécutions */
export const getExecutions = (params?: { client?: string; status?: string; limit?: number }) =>
  api.get<Execution[]>('/executions', { params }).then(r => r.data)

/** Récupère le détail d'une exécution */
export const getExecution = (id: number) =>
  api.get<Execution>(`/executions/${id}`).then(r => r.data)

/** Récupère les logs d'une exécution (version HTTP) */
export const getExecutionLogs = (id: number) =>
  api.get<LogEntry[]>(`/executions/${id}/logs`).then(r => r.data)

/** Arrête une exécution en cours */
export const stopExecution = (id: number) =>
  api.delete(`/executions/${id}`).then(r => r.data)

// ---------------------------------------------------------------------------
// Variables de saisie — lire / écrire les fichiers de config
// ---------------------------------------------------------------------------

export interface VariableEntry {
  key: string
  value: string
  required: boolean
}

export interface VariablesResponse {
  client: string
  process: string
  file_path: string
  variables: VariableEntry[]
}

/** Lit le fichier de variables d'un processus */
export const getVariables = (client: string, process: string) =>
  api.get<VariablesResponse>(`/variables/${client}/${process}`).then(r => r.data)

/** Sauvegarde les variables d'un processus */
export const updateVariables = (client: string, process: string, variables: VariableEntry[]) =>
  api.put(`/variables/${client}/${process}`, { variables }).then(r => r.data)

/** Parse un contenu de fichier .txt de variables (même format que le backend) */
export function parseVariableFile(text: string): VariableEntry[] {
  const entries: VariableEntry[] = []
  for (const line of text.split(/\r?\n/)) {
    const s = line.trim()
    if (!s || s.startsWith('#')) continue
    const idx = s.indexOf('=')
    if (idx === -1) continue
    const key   = s.slice(0, idx).trim()
    const value = s.slice(idx + 1).trim()
    entries.push({ key, value, required: key.endsWith('*') })
  }
  return entries
}

// ---------------------------------------------------------------------------
// Screenshots — captures prises pendant un TNR
// ---------------------------------------------------------------------------

export interface ScreenshotFile {
  name: string
  path: string   // chemin relatif : "AWB/megacommon/position/screen_123.png"
  size: number
}

export interface ScreenshotsInfo {
  count: number
  files: ScreenshotFile[]
}

/** Liste les captures d'une exécution */
export const getScreenshots = (id: number) =>
  api.get<ScreenshotsInfo>(`/executions/${id}/screenshots`).then(r => r.data)

/** URL de téléchargement ZIP (utilisée directement dans un <a href>) */
export const getScreenshotsDownloadUrl = (id: number) =>
  `/api/executions/${id}/screenshots/download`

/** URL d'une capture individuelle (pour <img src>) */
export const getScreenshotUrl = (id: number, path: string) =>
  `/api/executions/${id}/screenshots/${path}`
