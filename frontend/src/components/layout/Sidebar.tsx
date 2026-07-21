import { useEffect, useState, useRef } from 'react'
import {
  Plus, Trash2, Pin, LogOut,
  X, SquarePen, MessageSquare, MoreHorizontal
} from 'lucide-react'
import { useClerk, useUser } from '@clerk/clerk-react'
import { api } from '../../api.ts'
import type { Conversation, Usage } from '../../api.ts'

interface Props {
  currentConvId: string | null
  refreshTrigger: number
  onNewChat: () => void
  onSelectConv: (id: string) => void
  onClose: () => void
}

interface Props {
  usageRefresh?: number
}

export default function Sidebar({ currentConvId, refreshTrigger, onNewChat, onSelectConv, onClose }: Props) {
  const { user } = useUser()
  const { signOut } = useClerk()
  const [convs, setConvs] = useState<Conversation[]>([])
  const [loading, setLoading] = useState(true)
  const [hovered, setHovered] = useState<string | null>(null)
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null)
  const menuRef = useRef<HTMLDivElement | null>(null)
  const [usage, setUsage] = useState<Usage | null>(null)
  const [loadingUsage, setLoadingUsage] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getConversations()
      .then(setConvs)
      .catch(() => setConvs([]))
      .finally(() => setLoading(false))

    setLoadingUsage(true)
    api.getUsage()
      .then((data) => {
        setUsage(data)
      })
      .catch((err) => {
        console.error("Usage fetch failed:", err)
        setUsage(null)
      })
      .finally(() => setLoadingUsage(false))
  }, [refreshTrigger])

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpenId(null)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const del = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    setMenuOpenId(null)
    setConvs(p => p.filter(c => c.id !== id))
    await api.deleteConversation(id).catch(() => {})
  }

  const pin = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    setMenuOpenId(null)
    await api.pinConversation(id).catch(() => {})
    api.getConversations().then(setConvs).catch(() => {})
  }

  // Derived usage metrics with fallback values
  const displayPercentage = usage ? Math.min(usage.usage_percentage, 100) : 0
  const displayUsed = usage?.tokens_used ?? 0
  const displayLimit = usage?.tokens_limit ?? 100000

  return (
    <div
      className="h-full flex flex-col select-none"
      style={{ background: '#111111', borderRight: '1px solid rgba(255,255,255,0.06)' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <div className="flex items-center gap-2">
          <div
            className="w-6 h-6 rounded-lg flex items-center justify-center shrink-0"
            style={{ background: 'linear-gradient(135deg, #00d4aa, #009e80)' }}
          >
            <svg width="11" height="11" viewBox="0 0 14 14" fill="none">
              <path d="M7 1C7 1 3.5 5 3.5 8C3.5 10 5.1 11.5 7 11.5C8.9 11.5 10.5 10 10.5 8C10.5 6 9 4.5 9 4.5C9 4.5 8.5 7 7 7C5.5 7 5.5 4.5 7 1Z" fill="black"/>
            </svg>
          </div>
          <span style={{ color: '#e0e0e0', fontSize: 14, fontWeight: 600 }}>Surge</span>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={onNewChat}
            title="New chat"
            className="p-1.5 rounded-lg transition-colors"
            style={{ color: '#555' }}
            onMouseEnter={e => (e.currentTarget.style.color = '#aaa')}
            onMouseLeave={e => (e.currentTarget.style.color = '#555')}
          >
            <SquarePen size={15} />
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg transition-colors lg:hidden"
            style={{ color: '#555' }}
            onMouseEnter={e => (e.currentTarget.style.color = '#aaa')}
            onMouseLeave={e => (e.currentTarget.style.color = '#555')}
          >
            <X size={15} />
          </button>
        </div>
      </div>

      {/* New chat button */}
      <div className="px-3 mt-2 mb-4">
        <button
          onClick={onNewChat}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-[14px] transition-all"
          style={{
            color: '#aaa',
            background: 'transparent',
            border: '1px solid transparent',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.color = '#fff'
            e.currentTarget.style.background = 'rgba(255,255,255,0.05)'
            e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)'
          }}
          onMouseLeave={e => {
            e.currentTarget.style.color = '#aaa'
            e.currentTarget.style.background = 'transparent'
            e.currentTarget.style.borderColor = 'transparent'
          }}
        >
          <Plus size={15} style={{ color: '#aaa' }} />
          New chat
        </button>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto px-2 min-h-0">
        {convs.length > 0 && (
          <p
            className="px-3 mb-2 text-[13px] font-medium"
            style={{ color: '#777777' }}
          >
            Recents
          </p>
        )}

        {loading && (
          <p className="px-3 py-2 text-[12px]" style={{ color: '#555' }}>
            Loading…
          </p>
        )}

        {!loading && convs.length === 0 && (
          <div className="flex flex-col items-center py-10 px-4 text-center">
            <MessageSquare size={28} style={{ color: '#222', marginBottom: 10 }} />
            <p style={{ color: '#333', fontSize: 13 }}>No conversations yet</p>
            <p style={{ color: '#252525', fontSize: 12, marginTop: 4 }}>
              Start a new chat to get going
            </p>
          </div>
        )}

        <div className="space-y-0.5">
          {convs.map(c => {
            const active = currentConvId === c.id
            const isHov = hovered === c.id
            const isMenuOpen = menuOpenId === c.id

            return (
              <div
                key={c.id}
                onClick={() => onSelectConv(c.id)}
                onMouseEnter={() => setHovered(c.id)}
                onMouseLeave={() => setHovered(null)}
                className="relative flex items-center justify-between px-3 py-1.5 rounded-lg cursor-pointer transition-all duration-100"
                style={{
                  background: active || isMenuOpen
                    ? 'rgba(255,255,255,0.06)'
                    : isHov
                    ? 'rgba(255,255,255,0.03)'
                    : 'transparent',
                }}
              >
                <div className="flex-1 min-w-0 pr-2">
                  <p
                    className="text-[14px] truncate leading-normal"
                    style={{ 
                      color: active || isMenuOpen ? '#ffffff' : isHov ? '#e0e0e0' : '#b0b0b0',
                      fontWeight: active ? '500' : '400'
                    }}
                  >
                    {c.title}
                  </p>
                </div>

                <div className="w-5 h-5 flex items-center justify-center shrink-0 relative">
                  {(isHov || active || isMenuOpen) && (
                    <button
                      onClick={e => {
                        e.stopPropagation();
                        setMenuOpenId(isMenuOpen ? null : c.id);
                      }}
                      className="p-0.5 rounded-md transition-colors"
                      style={{ color: active || isMenuOpen ? '#ffffff' : '#777' }}
                      onMouseEnter={e => (e.currentTarget.style.color = '#fff')}
                      onMouseLeave={e => (e.currentTarget.style.color = active || isMenuOpen ? '#ffffff' : '#777')}
                    >
                      <MoreHorizontal size={14} />
                    </button>
                  )}

                  {isMenuOpen && (
                    <div
                      ref={menuRef}
                      className="absolute right-0 top-6 z-50 w-28 rounded-lg shadow-xl py-1 text-[12px] border"
                      style={{ background: '#181818', borderColor: '#262626' }}
                    >
                      <button
                        onClick={e => pin(e, c.id)}
                        className="w-full text-left px-3 py-1.5 flex items-center gap-2"
                        style={{ color: '#b0b0b0' }}
                        onMouseEnter={e => { e.currentTarget.style.background = '#222'; e.currentTarget.style.color = '#fff'; }}
                        onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#b0b0b0'; }}
                      >
                        <Pin size={12} style={{ color: c.is_pinned ? '#00d4aa' : 'inherit' }} />
                        {c.is_pinned ? 'Unpin' : 'Pin'}
                      </button>
                      <button
                        onClick={e => del(e, c.id)}
                        className="w-full text-left px-3 py-1.5 flex items-center gap-2"
                        style={{ color: '#ef4444' }}
                        onMouseEnter={e => { e.currentTarget.style.background = 'rgba(239,68,68,0.08)'; }}
                        onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                      >
                        <Trash2 size={12} />
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* User Section Footer */}
      <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', padding: '12px' }} className="flex flex-col gap-3">
        
        {/* Usage Card Module Connected to Database */}
        <div 
          className="rounded-xl p-3.5 border flex flex-col gap-2"
          style={{ 
            background: 'rgba(255,255,255,0.01)', 
            borderColor: 'rgba(255,255,255,0.04)' 
          }}
        >
          <div className="flex items-center justify-between">
            <span style={{ color: '#888888', fontSize: '11px', fontWeight: 500, letterSpacing: '0.03em' }}>
              USAGE
            </span>
          </div>
          
          <div className="flex items-baseline justify-between mt-0.5">
            <span style={{ color: '#ffffff', fontSize: '18px', fontWeight: 600, fontFamily: 'monospace' }}>
              {loadingUsage ? '...' : `${displayPercentage}%`}
            </span>
          </div>

          {/* Progress Bar Track */}
          <div className="w-full h-1.5 rounded-full overflow-hidden" style={{ background: '#1c1c1c' }}>
            <div 
              className="h-full rounded-full transition-all duration-300" 
              style={{ 
                width: `${displayPercentage}%`, 
                background: 'linear-gradient(90deg, #00a882, #00e6b8)' 
              }} 
            />
          </div>

          <div className="flex justify-between items-center text-[11px]" style={{ color: '#555555' }}>
            <span>
              {loadingUsage ? (
                'Loading tokens...'
              ) : (
                `${displayUsed.toLocaleString()} / ${displayLimit.toLocaleString()} tokens`
              )}
            </span>
          </div>
        </div>

        {/* User Profile Info Section */}
        <div
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl cursor-pointer transition-all group"
          style={{ background: 'transparent' }}
          onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.04)')}
          onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
        >
          <img
            src={user?.imageUrl || `https://api.dicebear.com/7.x/initials/svg?seed=${user?.firstName || 'Trevor'}`}
            alt=""
            className="w-7 h-7 rounded-lg object-cover shrink-0"
            style={{ border: '1px solid rgba(255,255,255,0.08)' }}
          />
          <div className="flex-1 min-w-0">
            <p
              className="text-[13px] font-medium truncate"
              style={{ color: '#c0c0c0' }}
            >
              {user?.firstName ? `${user.firstName} ${user.lastName || ''}` : 'Trevor Hihu'}
            </p>
            <p className="text-[11px]" style={{ color: '#00a882' }}>
              Free plan
            </p>
          </div>
          <button
            onClick={() => signOut()}
            className="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-all"
            style={{ color: '#555' }}
            onMouseEnter={e => (e.currentTarget.style.color = '#ef4444')}
            onMouseLeave={e => (e.currentTarget.style.color = '#555')}
            title="Sign out"
          >
            <LogOut size={13} />
          </button>
        </div>

      </div>
    </div>
  )
}