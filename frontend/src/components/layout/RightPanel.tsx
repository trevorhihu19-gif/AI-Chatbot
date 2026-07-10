import { X, Globe, Code, FileText, Image, Database, Plus, Wrench } from 'lucide-react'

interface RightPanelProps {
  onClose: () => void
}

const tools = [
  { icon: Globe,    label: 'Web Search',     desc: 'Search the web for real-time information', enabled: true },
  { icon: Code,     label: 'Code Interpreter', desc: 'Run code and analyze data',             enabled: true },
  { icon: FileText, label: 'Document Reader', desc: 'Extract and understand any document',    enabled: true },
  { icon: Image,    label: 'Image Generator', desc: 'Generate images from your description',  enabled: false },
  { icon: Database, label: 'Knowledge Base',  desc: 'Use your uploaded documents',            enabled: true },
]

const files = [
  { name: 'Product_Requirements.pdf', size: '2.4 MB', time: 'Just now',  color: '#ff4444' },
  { name: 'Market_Research.csv',      size: '1.1 MB', time: '10m ago',   color: '#00d4aa' },
  { name: 'Brand_Guidelines.pdf',     size: '3.2 MB', time: '1h ago',    color: '#ff4444' },
]

interface ToggleProps {
  enabled: boolean
  onChange: () => void
}

function Toggle({ enabled, onChange }: ToggleProps) {
  return (
    <button
      onClick={onChange}
      className="relative w-9 h-5 rounded-full transition-colors duration-200 flex-shrink-0"
      style={{ background: enabled ? '#00d4aa' : '#2a2a2a' }}
    >
      <div
        className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform duration-200"
        style={{ transform: enabled ? 'translateX(20px)' : 'translateX(2px)' }}
      />
    </button>
  )
}

export default function RightPanel({ onClose }: RightPanelProps) {
  return (
    <div
      className="h-full flex flex-col overflow-y-auto"
      style={{
        background: 'rgba(17,17,17,0.85)',
        backdropFilter: 'blur(20px)',
        borderLeft: '1px solid #2a2a2a',
      }}
    >
      {/* Mobile close handle */}
      <div className="flex justify-center pt-3 pb-1 lg:hidden">
        <div className="w-8 h-1 rounded-full bg-[#2a2a2a]" />
      </div>

      {/* ── Tools section ── */}
      <div className="px-4 pt-4 pb-2">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Wrench size={14} className="text-[#888]" />
            <span className="text-white text-sm font-semibold">Tools</span>
          </div>
          <div className="flex items-center gap-2">
            <button className="text-[#00d4aa] text-xs hover:underline">View all</button>
            <button onClick={onClose} className="lg:hidden text-[#555] hover:text-white transition-colors">
              <X size={16} />
            </button>
          </div>
        </div>

        <div className="space-y-3">
          {tools.map(tool => (
            <div key={tool.label} className="flex items-start gap-3">
              <div
                className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
                style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid #2a2a2a' }}
              >
                <tool.icon size={13} className="text-[#00d4aa]" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-white text-xs font-medium">{tool.label}</p>
                <p className="text-[#555] text-xs leading-relaxed">{tool.desc}</p>
              </div>
              <Toggle enabled={tool.enabled} onChange={() => {}} />
            </div>
          ))}
        </div>
      </div>

      <div className="mx-4 my-3" style={{ borderTop: '1px solid #2a2a2a' }} />

      {/* ── Files section ── */}
      <div className="px-4 pb-2">
        <div className="flex items-center justify-between mb-3">
          <span className="text-white text-sm font-semibold">Files</span>
          <button
            className="flex items-center gap-1 text-xs text-[#888] hover:text-white transition-colors"
          >
            <Plus size={12} />
            Add
          </button>
        </div>

        <div className="space-y-2">
          {files.map(file => (
            <div
              key={file.name}
              className="flex items-center gap-3 p-2 rounded-lg transition-colors duration-150"
              style={{ background: 'rgba(255,255,255,0.03)' }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.06)'}
              onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.03)'}
            >
              <div
                className="w-6 h-7 rounded flex items-center justify-center flex-shrink-0"
                style={{ background: `${file.color}22`, border: `1px solid ${file.color}44` }}
              >
                <FileText size={11} style={{ color: file.color }} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-white text-xs font-medium truncate">{file.name}</p>
                <p className="text-[#555] text-xs">{file.size} · {file.time}</p>
              </div>
            </div>
          ))}
        </div>

        <button className="mt-2 text-xs text-[#555] hover:text-[#888] transition-colors">
          View all files →
        </button>
      </div>

      <div className="mx-4 my-3" style={{ borderTop: '1px solid #2a2a2a' }} />

      {/* ── Usage section ── */}
      <div className="px-4 pb-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-white text-sm font-semibold">Usage</span>
          <button className="text-xs text-[#888] hover:text-white transition-colors">
            This month ▾
          </button>
        </div>

        <div className="mb-2 flex items-end gap-1">
          <span className="text-white text-3xl font-bold">78%</span>
          <span className="text-[#888] text-sm mb-1">of monthly limit</span>
        </div>

        {/* Progress bar */}
        <div className="h-1.5 rounded-full overflow-hidden" style={{ background: '#2a2a2a' }}>
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: '78%',
              background: 'linear-gradient(90deg, #00d4aa, #00b896)',
            }}
          />
        </div>

        <p className="text-[#555] text-xs mt-2">7,800 / 10,000 credits</p>
      </div>
    </div>
  )
}
