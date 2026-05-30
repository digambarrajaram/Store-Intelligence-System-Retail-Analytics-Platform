import React, { useEffect, useState } from 'react'

function App() {
  const [analytics, setAnalytics] = useState(null)
  const [alerts, setAlerts] = useState<Array<any>>([])

  useEffect(() => {
    // Fetch analytics
    fetch('http://localhost:8000/api/v1/analytics')
      .then(res => res.json())
      .then(data => setAnalytics(data))
      .catch(err => console.error('Failed to fetch analytics', err))

    // WebSocket for alerts
    const ws = new WebSocket('ws://localhost:8000/ws/alerts')
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      setAlerts(prev => [data, ...prev.slice(0, 9)]) // keep last 10
    }
    ws.onopen = () => console.log('WebSocket connected')
    ws.onclose = () => console.log('WebSocket disconnected')
    return () => ws.close()
  }, [])

  return (
    <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>
      <h1>CV Pipeline Dashboard</h1>
      {analytics ? (
        <div>
          <h2>Analytics</h2>
          <p>Total detections: {analytics.total_detections}</p>
          <p>Unique tracks: {analytics.unique_tracks}</p>
          <p>Anomaly count: {analytics.anomaly_count}</p>
          <p>Avg FPS: {analytics.avg_fps.toFixed(1)}</p>
          <p>Peak crowd: {analytics.peak_crowd_size}</p>
        </div>
      ) : <p>Loading analytics...</p>}
      <h2>Recent Alerts</h2>
      {alerts.length === 0 ? (
        <p>No alerts yet</p>
      ) : (
        <ul>
          {alerts.map((alert, idx) => (
            <li key={idx}>
              [{alert.anomaly_type}] {alert.camera_id} at {new Date(alert.timestamp * 1000).toLocaleTimeString()}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default App