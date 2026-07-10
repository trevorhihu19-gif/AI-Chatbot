import { useState } from 'react'
import { Menu, PanelRight } from 'lucide-react'
import AnimatedBackground from './AnimatedBackground'
import Sidebar from './Sidebar'
import RightPanel from './RightPanel'

interface AppLayoutProps {
  children: React.ReactNode
}

export default function AppLayout({ children }: AppLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [rightPanelOpen, setRightPanelOpen] = useState(true)  

  return (
    <div className="relative flex h-screen overflow-hidden">

      <AnimatedBackground />

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed top-0 left-0 h-full z-50 w-[260px]
          transform transition-transform duration-300 ease-in-out
          lg:relative lg:translate-x-0 lg:z-auto lg:flex-shrink-0
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <Sidebar onClose={() => setSidebarOpen(false)} />
      </aside>

      {/* Main area */}
      <main className="relative flex-1 flex flex-col min-w-0 overflow-hidden">

        {/* Top bar */}
        <div
          className="flex items-center justify-between px-4 py-2 flex-shrink-0"
          style={{ borderBottom: '1px solid #1a1a1a' }}
        >
          {/* Left: mobile hamburger + model selector */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 rounded-lg text-[#888] hover:text-white hover:bg-[#1a1a1a] transition-colors"
            >
              <Menu size={18} />
            </button>

            {/* Model selector pill */}
            <button
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors"
              style={{
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid #2a2a2a',
                color: '#f0f0f0',
              }}
            >
              <span>Surge 1.0</span>
              <span className="text-[#555]">▾</span>
            </button>
          </div>

          {/* Right: actions + toggle right panel */}
          <div className="flex items-center gap-2">
            <button className="p-2 rounded-lg text-[#555] hover:text-white hover:bg-[#1a1a1a] transition-colors">
              ☆
            </button>
            <button className="p-2 rounded-lg text-[#555] hover:text-white hover:bg-[#1a1a1a] transition-colors">
              ↑
            </button>

            {/* Toggle right panel button */}
            <button
              onClick={() => setRightPanelOpen(!rightPanelOpen)}
              className="p-2 rounded-lg transition-colors"
              style={{
                color: rightPanelOpen ? '#00d4aa' : '#555',
                background: rightPanelOpen ? 'rgba(0,212,170,0.08)' : 'transparent',
              }}
              title={rightPanelOpen ? 'Hide panel' : 'Show panel'}
            >
              <PanelRight size={18} />
            </button>
          </div>
        </div>

        {/* Page content */}
        <div className="flex-1 overflow-hidden">
          {children}
        </div>
      </main>

      {/* Right panel — slides in/out */}
      <aside
        className={`
          flex-shrink-0 overflow-hidden
          transition-all duration-300 ease-in-out
          ${rightPanelOpen ? 'w-[300px]' : 'w-0'}
          hidden lg:block
        `}
      >
        <div className="w-[300px] h-full">
          <RightPanel onClose={() => setRightPanelOpen(false)} />
        </div>
      </aside>

      {/* Mobile right panel — bottom sheet */}
      {rightPanelOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={() => setRightPanelOpen(false)}
        />
      )}
      <aside
        className={`
          fixed bottom-0 left-0 right-0 z-50 h-[75vh] rounded-t-2xl
          transform transition-transform duration-300 ease-in-out
          lg:hidden
          ${rightPanelOpen ? 'translate-y-0' : 'translate-y-full'}
        `}
      >
        <RightPanel onClose={() => setRightPanelOpen(false)} />
      </aside>

    </div>
  )
}