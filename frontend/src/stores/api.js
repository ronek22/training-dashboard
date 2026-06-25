import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const useApi = () => ({
  getDashboard: () => api.get('/dashboard'),
  getTrainingLoad: (params) => api.get('/training-load', { params }),
  getGoals: (params) => api.get('/goals', { params }),
  createGoal: (payload) => api.post('/goals', payload),
  getActivities: (params) => api.get('/activities', { params }),
  getCalendarWeeks: (params) => api.get('/calendar/weeks', { params }),
  getWeeklyPlans: (params) => api.get('/plans/weekly', { params }),
  adjustWeeklyPlan: (payload) => api.post('/plans/weekly/adjust', payload),
  getStravaStatus: () => api.get('/integrations/strava/status'),
  importStravaActivities: (payload) => api.post('/integrations/strava/import', payload),
  backfillStravaStreams: (payload) => api.post('/integrations/strava/streams/backfill', payload),
  getNotes: (params) => api.get('/notes', { params }),
  getWeekly: () => api.get('/weekly'),
  getMetric: (name) => api.get(`/metrics/${name}`),
  createMetric: (payload) => api.post('/metrics', payload),
})
