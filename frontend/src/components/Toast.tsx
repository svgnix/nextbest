import { motion } from 'framer-motion'
import './Toast.css'

interface ToastProps {
  message: string
}

export default function Toast({ message }: ToastProps) {
  return (
    <motion.div
      className="toast"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 8 }}
      transition={{ duration: 0.2 }}
    >
      {message}
    </motion.div>
  )
}
