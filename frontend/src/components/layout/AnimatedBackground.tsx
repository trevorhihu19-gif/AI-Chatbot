import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'

// ── Stars ──────────────────────────────────────────────────────────────────

const generateStaticStars = () => {
  return Array.from({ length: 80 }, (_, i) => ({
    id: i,
    x: Math.random() * 100,
    y: Math.random() * 100,
    size: Math.random() * 1.5 + 0.5,
    duration: Math.random() * 3 + 2,
    delay: Math.random() * 4,
  }));
};

function Stars() {
  const [stars] = useState(generateStaticStars);

  return (
    <div className="absolute inset-0 overflow-hidden">
      {stars.map(star => (
        <motion.div
          key={star.id}
          className="absolute rounded-full bg-white"
          style={{
            left: `${star.x}%`,
            top: `${star.y}%`,
            width: star.size,
            height: star.size,
          }}
          animate={{
            opacity: [0.1, 0.8, 0.1],
            scale: [1, 1.3, 1],
          }}
          transition={{
            duration: star.duration,
            delay: star.delay,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
      ))}
    </div>
  )
}

// ── Aurora Glow Blobs ─────────────────────────────────────────────────────

function AuroraBlobs() {
  return (
    <div className="absolute inset-0 overflow-hidden">
      {/* Emerald blob — top left */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: '600px',
          height: '600px',
          top: '-100px',
          left: '-100px',
          background: 'radial-gradient(circle, rgba(0, 212, 170, 0.15) 0%, transparent 70%)',
          filter: 'blur(60px)',
        }}
        animate={{
          x: [0, 80, -40, 0],
          y: [0, 60, 100, 0],
          scale: [1, 1.1, 0.95, 1],
        }}
        transition={{
          duration: 18,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      {/* Warm orange blob — bottom right */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: '700px',
          height: '700px',
          bottom: '-150px',
          right: '-150px',
          background: 'radial-gradient(circle, rgba(255, 140, 50, 0.12) 0%, transparent 70%)',
          filter: 'blur(80px)',
        }}
        animate={{
          x: [0, -60, 40, 0],
          y: [0, -80, -40, 0],
          scale: [1, 0.9, 1.1, 1],
        }}
        transition={{
          duration: 22,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      {/* Teal blob — center */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: '400px',
          height: '400px',
          top: '40%',
          left: '40%',
          background: 'radial-gradient(circle, rgba(0, 180, 150, 0.08) 0%, transparent 70%)',
          filter: 'blur(50px)',
        }}
        animate={{
          x: [0, 100, -50, 0],
          y: [0, -60, 80, 0],
          scale: [1, 1.2, 0.9, 1],
        }}
        transition={{
          duration: 25,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />
    </div>
  )
}

// ── Film Grain Overlay ────────────────────────────────────────────────────

function FilmGrain() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    canvas.width = window.innerWidth
    canvas.height = window.innerHeight

    let animationId: number

    const render = () => {
      // Generate random noise pixels
      const imageData = ctx.createImageData(canvas.width, canvas.height)
      const data = imageData.data

      for (let i = 0; i < data.length; i += 4) {
        const noise = Math.random() * 15  // subtle — not too strong
        data[i] = noise
        data[i + 1] = noise
        data[i + 2] = noise
        data[i + 3] = Math.random() * 20  // very low opacity
      }

      ctx.putImageData(imageData, 0, 0)
      animationId = requestAnimationFrame(render)
    }

    render()

    return () => cancelAnimationFrame(animationId)
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 pointer-events-none"
      style={{ opacity: 0.4, mixBlendMode: 'overlay' }}
    />
  )
}

// ── Floating Particles ────────────────────────────────────────────────────

const staticParticles = Array.from({ length: 60 }, (_, i) => ({
  id: i,
  x: Math.random() * 100,
  y: Math.random() * 100,
  size: Math.random() * 3 + 1,
  duration: Math.random() * 20 + 15,
  delay: Math.random() * 10,
  color: ['#00d4aa', '#ff8c32', '#00b896'][Math.floor(Math.random() * 3)],
  moveX: [0, Math.random() * 100 - 50, Math.random() * 100 - 50, 0] as number[],
  moveY: [0, Math.random() * 100 - 50, Math.random() * 100 - 50, 0] as number[],
}))

function FloatingParticles() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {staticParticles.map(p => (
        <motion.div
          key={p.id}
          className="absolute rounded-full"
          style={{
            left: `${p.x}%`,
            top: `${p.y}%`,
            width: p.size,
            height: p.size,
            background: p.color,
            boxShadow: `0 0 ${p.size * 2}px ${p.color}`,
          }}
          animate={{
            x: p.moveX,
            y: p.moveY,
            opacity: [0.1, 0.4, 0.1],
          }}
          transition={{
            duration: p.duration,
            delay: p.delay,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
      ))}
    </div>
  )
}
// ── Main Component ────────────────────────────────────────────────────────

export default function AnimatedBackground() {
  return (
    <div
      className="fixed inset-0 -z-10"
      style={{ background: '#09090B' }}
    >
      <AuroraBlobs />
      <Stars />
      <FloatingParticles />
      <FilmGrain />
    </div>
  )
}