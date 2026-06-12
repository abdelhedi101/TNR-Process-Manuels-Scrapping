/**
 * App.tsx — Racine de l'application React
 *
 * C'est ici qu'on :
 * 1. Configure le routeur (quelle URL = quelle page)
 * 2. Configure TanStack Query (pour les appels API)
 * 3. Définit le layout global (Sidebar + contenu)
 */

import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import Sidebar    from './components/Sidebar'
import Dashboard  from './pages/Dashboard'
import Execute    from './pages/Execute'
import Monitor    from './pages/Monitor'
import History    from './pages/History'

// QueryClient : le gestionnaire de cache pour tous les appels API
// staleTime: 30s → les données ne sont pas rechargées pendant 30 secondes
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
})

export default function App() {
  return (
    // QueryClientProvider : rend le queryClient disponible dans toute l'app
    <QueryClientProvider client={queryClient}>

      {/* BrowserRouter : active la navigation entre pages */}
      <BrowserRouter>
        <div className="flex min-h-screen bg-[#0f1117]">

          {/* Sidebar fixe à gauche */}
          <Sidebar />

          {/* Contenu principal — décalé de 240px (largeur sidebar) */}
          <main className="flex-1 ml-60 overflow-auto">
            <Routes>
              {/* Route "/" → Dashboard (page d'accueil) */}
              <Route path="/"           element={<Dashboard />} />

              {/* Route "/execute" → Page de lancement */}
              <Route path="/execute"    element={<Execute />} />

              {/* Route "/monitor/:id" → Page de monitoring
                  :id est dynamique : /monitor/1, /monitor/42, etc. */}
              <Route path="/monitor/:id" element={<Monitor />} />

              {/* Route "/history" → Historique */}
              <Route path="/history"    element={<History />} />

              {/* Pages à venir (placeholder) */}
              <Route path="/projects/*" element={<ComingSoon title="Projets" />} />
              <Route path="/config"     element={<ComingSoon title="Configuration" />} />
              <Route path="/docs"       element={<ComingSoon title="Documentation" />} />
            </Routes>
          </main>

        </div>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

// Page temporaire pour les sections pas encore développées
function ComingSoon({ title }: { title: string }) {
  return (
    <div className="p-8 flex items-center justify-center min-h-64">
      <div className="text-center">
        <p className="text-white text-xl font-semibold mb-2">{title}</p>
        <p className="text-[#64748b] text-sm">Cette section sera disponible dans la prochaine phase.</p>
      </div>
    </div>
  )
}
