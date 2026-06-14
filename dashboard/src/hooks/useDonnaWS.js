import { useEffect, useRef, useCallback } from 'react'
import { WS_URL } from '../lib/constants.js'

const RECONNECT_MS = 3000

export function useDonnaWS(onEvent) {
  const wsRef = useRef(null)
  const timerRef = useRef(null)
  const onEventRef = useRef(onEvent)

  // Keep ref current so WebSocket callbacks always have latest handler
  useEffect(() => {
    onEventRef.current = onEvent
  })

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) return

    let ws
    try {
      ws = new WebSocket(WS_URL)
    } catch {
      timerRef.current = setTimeout(connect, RECONNECT_MS)
      return
    }

    wsRef.current = ws

    ws.onopen = () => {
      onEventRef.current({ type: '__connected' })
    }

    ws.onclose = () => {
      onEventRef.current({ type: '__disconnected' })
      timerRef.current = setTimeout(connect, RECONNECT_MS)
    }

    ws.onerror = () => {
      ws.close()
    }

    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data)
        onEventRef.current(event)
      } catch {
        // ignore malformed frames
      }
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(timerRef.current)
      if (wsRef.current) {
        wsRef.current.onclose = null // suppress reconnect on unmount
        wsRef.current.close()
      }
    }
  }, [connect])
}
