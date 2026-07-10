import { X, Plus, MessageSquare, Search, BookOpen, Bot, Wrench, Settings } from 'lucide-react'
import { useClerk, useUser } from '@clerk/clerk-react'

interface SidebarProps {
  onClose: () => void
}

const navItems = [
  { icon: MessageSquare, label: 'Chats', active: true },
  { icon: Search,        label: 'Search' },
  { icon: BookOpen,      label: 'Library' },
  { icon: Bot,           label: 'Agents' },
  { icon: Wrench,        label: 'Tools' },
  { icon: Settings,      label: 'Settings' },
]

const recentChats = [
  { label: 'AI product roadmap',       time: '2m ago' },
  { label: 'Market research summary',  time: '1h ago' },
  { label: 'Explain quantum computing',time: 'Yesterday' },
  { label: 'Create a marketing plan',  time: '2d ago' },
  { label: 'Python code optimization', time: '3d ago' },
]

export default function Sidebar({ onClose }: SidebarProps) {
  const { user } = useUser()
  const { signOut } = useClerk()

  return (
    <div
      className="h-full flex flex-col"
      style={{
        background: 'rgba(17,17,17,0.85)',
        backdropFilter: 'blur(20px)',
        borderRight: '1px solid #2a2a2a',
      }}
    >
      {/* ── Header ── */}
      <div className="flex items-center justify-between px-4 py-4">
        <div className="flex items-center gap-2">
          {/* Surge logo mark */}
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center"
            style={{ background: 'linear-gradient(135deg, #00d4aa, #00b896)' }}
          >
            <span className="text-black font-bold text-xs">S</span>
          </div>
          <span className="text-white font-semibold text-sm">Surge</span>
        </div>

        {/* Close button — mobile only */}
        <button
          onClick={onClose}
          className="lg:hidden p-1 rounded text-[#888] hover:text-white transition-colors"
        >
          <X size={18} />
        </button>
      </div>

      {/* ── New Chat button ── */}
      <div className="px-3 mb-4">
        <button
          className="w-full flex items-center justify-between px-3 py-2 rounded-xl text-sm font-medium transition-all duration-200"
          style={{
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid #2a2a2a',
            color: '#f0f0f0',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.background = 'rgba(255,255,255,0.08)'
            e.currentTarget.style.borderColor = '#3a3a3a'
          }}
          onMouseLeave={e => {
            e.currentTarget.style.background = 'rgba(255,255,255,0.05)'
            e.currentTarget.style.borderColor = '#2a2a2a'
          }}
        >
          <div className="flex items-center gap-2">
            <Plus size={16} />
            <span>New Chat</span>
          </div>
          <span className="text-[#555] text-xs">⌘K</span>
        </button>
      </div>

      {/* ── Nav items ── */}
      <nav className="px-3 space-y-0.5">
        {navItems.map(({ icon: Icon, label, active }) => (
          <button
            key={label}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-150"
            style={{
              color: active ? '#f0f0f0' : '#888',
              background: active ? 'rgba(255,255,255,0.07)' : 'transparent',
            }}
            onMouseEnter={e => {
              if (!active) {
                e.currentTarget.style.background = 'rgba(255,255,255,0.05)'
                e.currentTarget.style.color = '#f0f0f0'
              }
            }}
            onMouseLeave={e => {
              if (!active) {
                e.currentTarget.style.background = 'transparent'
                e.currentTarget.style.color = '#888'
              }
            }}
          >
            <Icon size={16} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      {/* ── Recent chats ── */}
      <div className="flex-1 overflow-y-auto mt-6 px-3">
        <p className="text-[#555] text-xs font-medium px-3 mb-2 uppercase tracking-wider">
          Recent Chats
        </p>
        <div className="space-y-0.5">
          {recentChats.map(chat => (
            <button
              key={chat.label}
              className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all duration-150 group"
              style={{ color: '#888' }}
              onMouseEnter={e => {
                e.currentTarget.style.background = 'rgba(255,255,255,0.05)'
                e.currentTarget.style.color = '#f0f0f0'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = 'transparent'
                e.currentTarget.style.color = '#888'
              }}
            >
              <span className="truncate text-left">{chat.label}</span>
              <span className="text-xs text-[#555] flex-shrink-0 ml-2">{chat.time}</span>
            </button>
          ))}
        </div>
        <button className="px-3 py-2 text-xs text-[#555] hover:text-[#888] transition-colors">
          View all chats →
        </button>
      </div>

      {/* ── Pro upgrade banner ── */}
      <div className="px-3 mb-3">
        <div
          className="p-3 rounded-xl"
          style={{
            background: 'linear-gradient(135deg, rgba(0,212,170,0.1), rgba(0,180,150,0.05))',
            border: '1px solid rgba(0,212,170,0.2)',
          }}
        >
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[#00d4aa]">◆</span>
            <span className="text-white text-xs font-semibold">Surge Pro</span>
          </div>
          <p className="text-[#888] text-xs mb-2">
            Unlock more power, higher limits, and advanced features.
          </p>
          <button
            className="w-full py-1.5 rounded-lg text-xs font-medium transition-all duration-200"
            style={{
              background: 'rgba(0,212,170,0.15)',
              color: '#00d4aa',
              border: '1px solid rgba(0,212,170,0.3)',
            }}
          >
            Upgrade Plan →
          </button>
        </div>
      </div>

      {/* ── User profile ── */}
      <div
        className="px-3 py-3 flex items-center gap-3"
        style={{ borderTop: '1px solid #2a2a2a' }}
      >
        <img
          src={user?.imageUrl || `https://api.dicebear.com/7.x/initials/svg?seed=${user?.firstName}`}
          alt="avatar"
          className="w-8 h-8 rounded-full object-cover flex-shrink-0"
          style={{ border: '1px solid #2a2a2a' }}
        />
        <div className="flex-1 min-w-0">
          <p className="text-white text-sm font-medium truncate">
            {user?.firstName} {user?.lastName}
          </p>
          <p className="text-[#00d4aa] text-xs">Pro Plan</p>
        </div>
        <button
          onClick={() => signOut()}
          className="text-[#555] hover:text-[#888] transition-colors text-xs"
        >
          ↗
        </button>
      </div>
    </div>
  )
}