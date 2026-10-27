import { ref } from 'vue'
import { requestError } from './plan-helpers.mjs'

// Minimum viable week: preview the shrunk rest of the week, apply it, or restore the full week.
export const useMinimumWeek = ({ api, flashMessage, refreshPlans }) => {
  const minimumWeek = ref(null)
  const minimumWeekPlan = ref(null)
  const minimumWeekBusy = ref(false)
  const minimumWeekError = ref('')

  const openMinimumWeek = async (plan) => {
    minimumWeekBusy.value = true
    try {
      minimumWeek.value = (await api.previewMinimumWeek(plan.week_start)).data
      minimumWeekPlan.value = plan
      minimumWeekError.value = ''
    } catch (error) {
      flashMessage.value = { type: 'error', title: 'Could not build a minimum week', detail: requestError(error, 'The preview request failed.') }
    } finally {
      minimumWeekBusy.value = false
    }
  }
  const closeMinimumWeek = () => { if (!minimumWeekBusy.value) minimumWeek.value = null }
  const applyMinimumWeek = async () => {
    minimumWeekBusy.value = true
    minimumWeekError.value = ''
    try {
      await api.applyMinimumWeek(minimumWeek.value.week_start)
      minimumWeek.value = null
      await refreshPlans()
    } catch (error) {
      minimumWeekError.value = requestError(error, 'Could not shrink the week.')
    } finally {
      minimumWeekBusy.value = false
    }
  }
  const restoreFullWeek = async (plan) => {
    minimumWeekBusy.value = true
    try {
      await api.restoreFullWeek(plan.week_start)
      await refreshPlans()
    } catch (error) {
      flashMessage.value = { type: 'error', title: 'Could not restore the week', detail: requestError(error, 'The restore request failed.') }
    } finally {
      minimumWeekBusy.value = false
    }
  }

  return { minimumWeek, minimumWeekPlan, minimumWeekBusy, minimumWeekError, openMinimumWeek, closeMinimumWeek, applyMinimumWeek, restoreFullWeek }
}
