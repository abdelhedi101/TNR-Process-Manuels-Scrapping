/**
 * Execute.tsx — Sélection client / module / processus
 *
 * Wizard en 3 étapes. Au choix du processus, redirige vers la page
 * de configuration des variables + lancement (/execute/:client/:module/:process).
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import {
  getClients, getModules, getProcesses,
  type Client, type Module, type ProcessType,
} from '../api/client'

export default function Execute() {
  const navigate = useNavigate()

  const [selectedClient, setSelectedClient] = useState<string | null>(null)
  const [selectedModule, setSelectedModule] = useState<string | null>(null)

  const step = selectedClient ? (selectedModule ? 3 : 2) : 1

  const { data: clients = [] } = useQuery({
    queryKey: ['clients'],
    queryFn:  getClients,
  })

  const { data: modules = [] } = useQuery({
    queryKey: ['modules', selectedClient],
    queryFn:  () => getModules(selectedClient!),
    enabled:  !!selectedClient,
  })

  const { data: processes = [] } = useQuery({
    queryKey: ['processes', selectedClient],
    queryFn:  () => getProcesses(selectedClient!),
    enabled:  !!selectedClient,
  })

  function handleProcess(slug: string) {
    navigate(`/execute/${selectedClient}/${selectedModule}/${slug}`)
  }

  function reset() {
    setSelectedClient(null)
    setSelectedModule(null)
  }

  return (
    <div className="p-8 w-full">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-white">Lancer une exécution</h1>
        <p className="text-[#64748b] text-sm mt-1">Sélectionnez le client, le module et le processus à exécuter</p>
      </div>

      {/* Indicateur d'étapes */}
      <div className="flex items-center gap-2 mb-8">
        {['Client', 'Module', 'Processus'].map((label, i) => {
          const stepNum  = i + 1
          const isDone   = step > stepNum
          const isActive = step === stepNum
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

      {/* Étape 1 — Client */}
      <Section title="1. Choisir le client" active={step >= 1}>
        <div className="grid grid-cols-3 gap-4">
          {clients.map((c: Client) => (
            <button
              key={c.slug}
              onClick={() => { setSelectedClient(c.slug); setSelectedModule(null) }}
              className={`p-5 rounded-xl border text-left transition-all ${
                selectedClient === c.slug
                  ? 'border-indigo-500 bg-indigo-600/10'
                  : 'border-[#2d3148] bg-[#1a1d27] hover:border-[#3d4158]'
              }`}
            >
              <p className="font-semibold text-white text-lg">{c.name}</p>
              <p className="text-[#64748b] text-sm mt-1">{c.full_name}</p>
              <p className="text-[#475569] text-xs mt-2">Auth: {c.auth_type}</p>
            </button>
          ))}
        </div>
      </Section>

      {/* Étape 2 — Module */}
      {selectedClient && (
        <Section title="2. Choisir le module" active={step >= 2}>
          <div className="grid grid-cols-3 gap-3">
            {modules.map((m: Module) => (
              <button
                key={m.slug}
                onClick={() => setSelectedModule(m.slug)}
                className={`p-4 rounded-xl border text-left transition-all ${
                  selectedModule === m.slug
                    ? 'border-indigo-500 bg-indigo-600/10'
                    : 'border-[#2d3148] bg-[#1a1d27] hover:border-[#3d4158]'
                }`}
              >
                <p className="font-medium text-white text-sm">{m.name}</p>
                <p className="text-[#475569] text-xs mt-1">Port {m.port}</p>
              </button>
            ))}
          </div>
        </Section>
      )}

      {/* Étape 3 — Processus → redirige directement */}
      {selectedModule && (
        <Section title="3. Choisir le processus" active={step >= 3}>
          <div className="grid grid-cols-2 gap-3">
            {processes.map((p: ProcessType) => (
              <button
                key={p.slug}
                onClick={() => handleProcess(p.slug)}
                className="p-4 rounded-xl border border-[#2d3148] bg-[#1a1d27] hover:border-indigo-500 hover:bg-indigo-600/10 text-left transition-all group"
              >
                <p className="font-medium text-white text-sm group-hover:text-indigo-300 transition-colors">{p.name}</p>
                <p className="text-[#64748b] text-xs mt-1">{p.description}</p>
                <p className="text-indigo-500 text-xs mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  Configurer & lancer →
                </p>
              </button>
            ))}
          </div>
          <button
            onClick={reset}
            className="mt-3 px-4 py-2 border border-[#2d3148] text-[#94a3b8] hover:text-white rounded-lg text-sm transition-colors"
          >
            Réinitialiser
          </button>
        </Section>
      )}
    </div>
  )
}

function Section({ title, active, children }: { title: string; active: boolean; children: React.ReactNode }) {
  return (
    <div className={`mb-6 transition-opacity ${active ? 'opacity-100' : 'opacity-40 pointer-events-none'}`}>
      <p className="text-[#94a3b8] text-sm font-medium mb-3">{title}</p>
      {children}
    </div>
  )
}
