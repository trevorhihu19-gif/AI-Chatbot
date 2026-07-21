import { useEffect, useRef } from 'react'
import { motion } from 'framer-motion'

const staticStars = Array.from({ length: 80 }, (_, i) => ({
  id: i,
  x: Math.random() * 100,
  y: Math.random() * 100,
  size: Math.random() * 1.5 + 0.5,
  duration: Math.random() * 3 + 2,
  delay: Math.random() * 4,
}))

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

function Stars() {
  return (
    <div className="absolute inset-0 overflow-hidden">
      {staticStars.map(star => (
        <motion.div
          key={star.id}
          className="absolute rounded-full bg-white"
          style={{
            left: `${star.x}%`,
            top: `${star.y}%`,
            width: star.size,
            height: star.size,
          }}
          animate={{ opacity: [0.1, 0.8, 0.1], scale: [1, 1.3, 1] }}
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

function AuroraBlobs() {
  return (
    <div className="absolute inset-0 overflow-hidden">
      {/* Strong emerald — top center */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: '900px',
          height: '900px',
          top: '-300px',
          left: '50%',
          transform: 'translateX(-50%)',
          background: 'radial-gradient(circle, rgba(0,180,100,0.25) 0%, rgba(0,150,80,0.1) 40%, transparent 70%)',
          filter: 'blur(80px)',
        }}
        animate={{ scale: [1, 1.1, 0.95, 1], y: [0, 40, -20, 0] }}
        transition={{ duration: 20, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Warm orange — bottom right */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: '700px',
          height: '700px',
          bottom: '-200px',
          right: '-100px',
          background: 'radial-gradient(circle, rgba(200,100,30,0.2) 0%, rgba(180,80,20,0.08) 40%, transparent 70%)',
          filter: 'blur(80px)',
        }}
        animate={{ scale: [1, 0.9, 1.05, 1], x: [0, -40, 20, 0] }}
        transition={{ duration: 25, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Teal accent — left */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: '500px',
          height: '500px',
          top: '30%',
          left: '-150px',
          background: 'radial-gradient(circle, rgba(0,212,170,0.1) 0%, transparent 70%)',
          filter: 'blur(60px)',
        }}
        animate={{ y: [0, -60, 40, 0], scale: [1, 1.15, 0.9, 1] }}
        transition={{ duration: 18, repeat: Infinity, ease: 'easeInOut' }}
      />
    </div>
  )
}

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
      const imageData = ctx.createImageData(canvas.width, canvas.height)
      const data = imageData.data
      for (let i = 0; i < data.length; i += 4) {
        const noise = Math.random() * 15
        data[i] = noise
        data[i + 1] = noise
        data[i + 2] = noise
        data[i + 3] = Math.random() * 20
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
      style={{ opacity: 0.35, mixBlendMode: 'overlay' }}
    />
  )
}

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
            boxShadow: `0 0 ${p.size * 3}px ${p.color}`,
          }}
          animate={{ x: p.moveX, y: p.moveY, opacity: [0.05, 0.35, 0.05] }}
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

export default function AnimatedBackground() {
  return (
    <div className="fixed inset-0 -z-10" style={{ background: '#09090B' }}>
      <AuroraBlobs />
      <Stars />
      <FloatingParticles />
      <FilmGrain />
    </div>
  )
}