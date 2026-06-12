/**
 * Execute.tsx — Page de lancement d'une exécution
 *
 * Formulaire en 3 étapes :
 *   1. Choisir le client (AWB / BMCE / CDG)
 *   2. Choisir le module (MegaCustody, MegaCor...)
 *   3. Choisir le processus (Saisie, TNR, SWIFT...)
 * Puis cliquer "Lancer" → redirige vers la page Monitor
 */

import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ChevronRight, Loader2 } from 'lucide-react'
import {
  getClients, getModules, getProcesses, createExecution,
  type Client, type Module, type ProcessType,
} from '../api/client'

export default function Execute() {
  const navigate = useNavigate()

  // État local : ce que l'utilisateur a sélectionné
  const [selectedClient,  setSelectedClient]  = useState<string | null>(null)
  const [selectedModule,  setSelectedModule]  = useState<string | null>(null)
  const [selectedProcess, setSelectedProcess] = useState<string | null>(null)

  // Étape actuelle du wizard (1, 2 ou 3)
  const step = selectedClient ? (selectedModule ? 3 : 2) : 1

  // Chargement des données depuis le backend
  const { data: clients = [] } = useQuery({
    queryKey: ['clients'],
    queryFn: getClients,
  })

  const { data: modules = [] } = useQuery({
    queryKey: ['modules', selectedClient],
    queryFn: () => getModules(selectedClient!),
    enabled: !!selectedClient, // ne charge que si un client est sélectionné
  })

  const { data: processes = [] } = useQuery({
    queryKey: ['processes', selectedClient],
    queryFn: () => getProcesses(selectedClient!),
    enabled: !!selectedClient,
  })

  // Mutation : action qui modifie des données (POST au backend)
  const launchMutation = useMutation({
    mutationFn: createExecution,
    onSuccess: (execution) => {
      // Rediriger vers la page de monitoring avec l'id de l'exécution
      navigate(`/monitor/${execution.id}`)
    },
  })

  function handleLaunch() {
    if (!selectedClient || !selectedModule || !selectedProcess) return
    launchMutation.mutate({
      client:  selectedClient,
      module:  selectedModule,
      process: selectedProcess,
    })
  }

  function reset() {
    setSelectedClient(null)
    setSelectedModule(null)
    setSelectedProcess(null)
  }

  return (
    <div className="p-8 max-w-4xl">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-white">Lancer une exécution</h1>
        <p className="text-[#64748b] text-sm mt-1">Sélectionnez le client, le module et le processus à exécuter</p>
      </div>

      {/* Indicateur d'étapes */}
      <div className="flex items-center gap-2 mb-8">
        {['Client', 'Module', 'Processus'].map((label, i) => {
          const stepNum = i + 1
          const isDone    = step > stepNum
          const isActive  = step === stepNum
          return (
            <div key={label} className="flex items-center gap-2">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
                isDone   ? 'bg-green-600 text-white' :
                isActive ? 'bg-indigo-600 text-white' :
                           'bg-[#2d3148] text-[#64748b]'
              }`}>
                {isDone ? '✓' : stepNum}
              </div>
              <span className={`text-sm ${isActive ? 'text-white' : 'text-[#64748b]'}`}>{label}</span>
              {i < 2 && <ChevronRight className="w-4 h-4 text-[#2d3148] mx-1" />}
            </div>
          )
        })}
      </div>

      {/* Étape 1 — Choisir le client */}
      <Section title="1. Choisir le client" active={step >= 1}>
        <div className="grid grid-cols-3 gap-4">
          {clients.map((client: Client) => (
            <button
              key={client.slug}
              onClick={() => { setSelectedClient(client.slug); setSelectedModule(null); setSelectedProcess(null) }}
              className={`p-5 rounded-xl border text-left transition-all ${
                selectedClient === client.slug
                  ? 'border-indigo-500 bg-indigo-600/10'
                  : 'border-[#2d3148] bg-[#1a1d27] hover:border-[#3d4158]'
              }`}
            >
              <p className="font-semibold text-white text-lg">{client.name}</p>
              <p className="text-[#64748b] text-sm mt-1">{client.full_name}</p>
              <p className="text-[#475569] text-xs mt-2">Auth: {client.auth_type}</p>
            </button>
          ))}
        </div>
      </Section>

      {/* Étape 2 — Choisir le module */}
      {selectedClient && (
        <Section title="2. Choisir le module" active={step >= 2}>
          <div className="grid grid-cols-3 gap-3">
            {modules.map((mod: Module) => (
              <button
                key={mod.slug}
                onClick={() => { setSelectedModule(mod.slug); setSelectedProcess(null) }}
                className={`p-4 rounded-xl border text-left transition-all ${
                  selectedModule === mod.slug
                    ? 'border-indigo-500 bg-indigo-600/10'
                    : 'border-[#2d3148] bg-[#1a1d27] hover:border-[#3d4158]'
                }`}
              >
                <p className="font-medium text-white text-sm">{mod.name}</p>
                <p className="text-[#475569] text-xs mt-1">Port {mod.port}</p>
              </button>
            ))}
          </div>
        </Section>
      )}

      {/* Étape 3 — Choisir le processus */}
      {selectedModule && (
        <Section title="3. Choisir le processus" active={step >= 3}>
          <div className="grid grid-cols-2 gap-3">
            {processes.map((proc: ProcessType) => (
              <button
                key={proc.slug}
                onClick={() => setSelectedProcess(proc.slug)}
                className={`p-4 rounded-xl border text-left transition-all ${
                  selectedProcess === proc.slug
                    ? 'border-indigo-500 bg-indigo-600/10'
                    : 'border-[#2d3148] bg-[#1a1d27] hover:border-[#3d4158]'
                }`}
              >
                <p className="font-medium text-white text-sm">{proc.name}</p>
                <p className="text-[#64748b] text-xs mt-1">{proc.description}</p>
              </button>
            ))}
          </div>
        </Section>
      )}

      {/* Récapitulatif + Bouton Lancer */}
      {selectedProcess && (
        <div className="mt-6 p-5 bg-[#1a1d27] border border-[#2d3148] rounded-xl">
          <p className="text-[#64748b] text-sm mb-3">Récapitulatif :</p>
          <div className="flex items-center gap-2 text-white text-sm mb-5">
            <span className="px-2 py-1 bg-[#2d3148] rounded">{selectedClient?.toUpperCase()}</span>
            <ChevronRight className="w-4 h-4 text-[#64748b]" />
            <span className="px-2 py-1 bg-[#2d3148] rounded">{selectedModule}</span>
            <ChevronRight className="w-4 h-4 text-[#64748b]" />
            <span className="px-2 py-1 bg-[#2d3148] rounded">{selectedProcess}</span>
          </div>
          <div className="flex gap-3">
            <button
              onClick={handleLaunch}
              disabled={launchMutation.isPending}
              className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg font-medium text-sm transition-colors"
            >
              {launchMutation.isPending
                ? <><Loader2 className="w-4 h-4 animate-spin" /> Lancement...</>
                : 'Lancer l\'exécution'
              }
            </button>
            <button onClick={reset} className="px-4 py-2.5 border border-[#2d3148] text-[#94a3b8] hover:text-white rounded-lg text-sm transition-colors">
              Réinitialiser
            </button>
          </div>
          {launchMutation.isError && (
            <p className="mt-3 text-red-400 text-sm">
              Erreur : {(launchMutation.error as any)?.response?.data?.detail || 'Erreur inconnue'}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

// Composant utilitaire : section avec titre
function Section({ title, active, children }: { title: string; active: boolean; children: React.ReactNode }) {
  return (
    <div className={`mb-6 transition-opacity ${active ? 'opacity-100' : 'opacity-40 pointer-events-none'}`}>
      <p className="text-[#94a3b8] text-sm font-medium mb-3">{title}</p>
      {children}
    </div>
  )
}
