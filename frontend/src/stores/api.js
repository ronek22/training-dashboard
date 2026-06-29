import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const useApi = () => ({
  getDashboard: () => api.get('/dashboard'),
  getPlanningStatus: () => api.get('/planning/status'),
  getWeeklyCoaching: (params) => api.get('/coaching/weekly', { params }),
  getTrainingLoad: (params) => api.get('/training-load', { params }),
  getGoals: (params) => api.get('/goals', { params }),
  createGoal: (payload) => api.post('/goals', payload),
  getActivities: (params) => api.get('/activities', { params }),
  updateActivityIntent: (activityId, payload) => api.post(`/activities/${activityId}/intent`, payload),
  linkActivityToPlan: (activityId, payload) => api.post(`/activities/${activityId}/link-plan`, payload),
  getActivityFeedback: (activityId) => api.get(`/activities/${activityId}/feedback`),
  saveActivityFeedback: (activityId, payload) => api.post(`/activities/${activityId}/feedback`, payload),
  getCalendarWeeks: (params) => api.get('/calendar/weeks', { params }),
  getWeeklyPlans: (params) => api.get('/plans/weekly', { params }),
  previewWeeklyPlanAdjustment: (payload) => api.post('/plans/weekly/adjust/preview', payload),
  adjustWeeklyPlan: (payload) => api.post('/plans/weekly/adjust', payload),
  getStravaStatus: () => api.get('/integrations/strava/status'),
  importStravaActivities: (payload) => api.post('/integrations/strava/import', payload),
  backfillStravaStreams: (payload) => api.post('/integrations/strava/streams/backfill', payload),
  getNotes: (params) => api.get('/notes', { params }),
  getWeekly: () => api.get('/weekly'),
  getMetric: (name) => api.get(`/metrics/${name}`),
  createMetric: (payload) => api.post('/metrics', payload),
})
