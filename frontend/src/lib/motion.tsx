import {
  animate,
  motion,
  useMotionValue,
  useReducedMotion,
  useSpring,
  useTransform,
  type Variants,
} from 'framer-motion'
import { useEffect, useRef, useState } from 'react'

/* Shared motion primitives for the Instrument-Grade Command Center.
 * Every effect degrades gracefully under prefers-reduced-motion and on
 * touch / no-hover devices where 3D tilt would feel wrong. */

export const EASE_OUT_EXPO = [0.16, 1, 0.3, 1] as const
export const EASE_IN_OUT_QUINT = [0.83, 0, 0.17, 1] as const
export const EASE_SPRING = [0.34, 1.56, 0.64, 1] as const

/** Staggered container — children fade-rise in sequence. */
export const staggerContainer: Variants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.06, delayChildren: 0.05 },
  },
}

/** Single child fade-rise. */
export const fadeRise: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.55, ease: EASE_OUT_EXPO },
  },
}

/** Quieter fade-rise for nested/secondary items. */
export const fadeRiseSoft: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: EASE_OUT_EXPO },
  },
}

/** True when the pointer can hover (i.e. not a coarse / touch pointer). */
function canHover(): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(hover: hover) and (pointer: fine)').matches
}

/**
 * Animated count-up. Returns a reactive number that eases from `from` to
 * `target` once `active` is true. Under reduced motion it snaps instantly.
 */
export function useCountUp(
  target: number,
  options: { from?: number; duration?: number; decimals?: number; active?: boolean } = {},
): number {
  const { from = 0, duration = 1.1, decimals = 0, active = true } = options
  const reduce = useReducedMotion()
  const [value, setValue] = useState<number>(reduce ? target : from)

  useEffect(() => {
    if (!active) return
    if (reduce) {
      setValue(target)
      return
    }
    const controls = animate(from, target, {
      duration,
      ease: EASE_OUT_EXPO,
      onUpdate: (v) => setValue(v),
    })
    return () => controls.stop()
  }, [target, from, duration, active, reduce])

  const factor = Math.pow(10, decimals)
  return Math.round(value * factor) / factor
}

interface CountUpProps {
  value: number
  decimals?: number
  prefix?: string
  suffix?: string
  duration?: number
  active?: boolean
  className?: string
}

/** Drop-in component that renders an animated, tabular-figured number. */
export function CountUp({
  value,
  decimals = 0,
  prefix = '',
  suffix = '',
  duration = 1.1,
  active = true,
  className,
}: CountUpProps) {
  const v = useCountUp(value, { decimals, duration, active })
  const text = v.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
  return (
    <span className={className} style={{ fontVariantNumeric: 'tabular-nums' }}>
      {prefix}
      {text}
      {suffix}
    </span>
  )
}

interface TiltResult {
  rotateX: ReturnType<typeof useSpring>
  rotateY: ReturnType<typeof useSpring>
  scale: ReturnType<typeof useSpring>
  handleMove: (e: React.MouseEvent<HTMLElement>) => void
  handleLeave: () => void
  enabled: boolean
}

/**
 * Cursor-tracked 3D tilt for cards. Returns spring-driven rotateX/rotateY
 * motion values plus pointer handlers. Disabled under reduced motion or on
 * touch/no-hover devices — callers should still pass the handlers through.
 */
export function useTilt(maxDeg = 7, scale = 1.012): TiltResult {
  const reduce = useReducedMotion()
  const hoverCapable = canHover()
  const enabled = !reduce && hoverCapable

  const px = useMotionValue(0)
  const py = useMotionValue(0)
  const spring = { stiffness: 140, damping: 16, mass: 0.4 }

  const rotateX = useSpring(useTransform(py, [-0.5, 0.5], [maxDeg, -maxDeg]), spring)
  const rotateY = useSpring(useTransform(px, [-0.5, 0.5], [-maxDeg, maxDeg]), spring)
  const scaleSpring = useSpring(useMotionValue(1), spring)

  const handleMove = (e: React.MouseEvent<HTMLElement>) => {
    if (!enabled) return
    const rect = e.currentTarget.getBoundingClientRect()
    px.set((e.clientX - rect.left) / rect.width - 0.5)
    py.set((e.clientY - rect.top) / rect.height - 0.5)
    scaleSpring.set(scale)
  }

  const handleLeave = () => {
    px.set(0)
    py.set(0)
    scaleSpring.set(1)
  }

  return { rotateX, rotateY, scale: scaleSpring, handleMove, handleLeave, enabled }
}

/**
 * Scroll-reveal via IntersectionObserver. Returns a ref + whether the element
 * has entered the viewport (sticky once revealed). framer-motion's whileInView
 * is the lighter alternative; this is for cases that need a persistent flag.
 */
export function useReveal<T extends HTMLElement = HTMLDivElement>(
  options: { threshold?: number; once?: boolean } = {},
): [React.RefObject<T>, boolean] {
  const { threshold = 0.2, once = true } = options
  const ref = useRef<T>(null)
  const [inView, setInView] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el || typeof IntersectionObserver === 'undefined') {
      setInView(true)
      return
    }
    const obs = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setInView(true)
            if (once) obs.disconnect()
          } else if (!once) {
            setInView(false)
          }
        }
      },
      { threshold, rootMargin: '0px 0px -8% 0px' },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [threshold, once])

  return [ref, inView]
}

/** Convenience wrapper so callers can `import { MotionDiv } from 'lib/motion'`. */
export const MotionDiv = motion.div
