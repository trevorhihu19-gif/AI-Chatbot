import { SignedIn, SignedOut, RedirectToSignIn } from '@clerk/clerk-react'
import { useState } from 'react'
import Sidebar from './components/layout/Sidebar.tsx'
import ChatPage from './pages/ChatPage'

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [currentConvId, setCurrentConvId] = useState<string | null>(null)
  const [sidebarRefresh, setSidebarRefresh] = useState(0)

  const triggerSidebarUpdate = () => setSidebarRefresh(p => p + 1)

  return (
    <>
      <SignedOut><RedirectToSignIn /></SignedOut>
      <SignedIn>
        <div className="flex h-full" style={{ background: '#0d0d0d' }}>

          {/* Mobile overlay */}
          {sidebarOpen && (
            <div
              className="fixed inset-0 z-30 lg:hidden"
              style={{ background: 'rgba(0,0,0,0.6)' }}
              onClick={() => setSidebarOpen(false)}
            />
          )}

          {/* Sidebar */}
          <div className={`
            fixed inset-y-0 left-0 z-40 w-60 shrink-0
            transition-transform duration-200 ease-in-out
            lg:relative lg:translate-x-0
            ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          `}>
            <Sidebar
              currentConvId={currentConvId}
              refreshTrigger={sidebarRefresh}
              onNewChat={() => { setCurrentConvId(null); setSidebarOpen(false) }}
              onSelectConv={(id) => { setCurrentConvId(id); setSidebarOpen(false) }}
              onClose={() => setSidebarOpen(false)}
            />
          </div>

          <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
            <ChatPage
              currentConvId={currentConvId}
              setCurrentConvId={setCurrentConvId}
              onNewConversation={triggerSidebarUpdate}
              onOpenSidebar={() => setSidebarOpen(true)}
            />
          </div>

        </div>
      </SignedIn>
    </>
  )
}