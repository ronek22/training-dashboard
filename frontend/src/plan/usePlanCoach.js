import { computed, onBeforeUnmount, ref } from 'vue'
import { format, startOfWeek } from 'date-fns'

const localCoachHostnames = new Set(['localhost', '127.0.0.1', '::1', '[::1]'])
const wait = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

export const coachBriefSuggestions = [
  'Prioritize recovery',
  'Keep Friday free',
  'Long ride on Saturday',
  'Limit weekday sessions to 60 minutes',
]
export const coachFeedbackSuggestions = [
  'Reduce the overall load',
  'Add another recovery day',
  'Move the hardest session later',
  'Keep the weekend lighter',
]

const appendSuggestion = (text, suggestion) => {
  if (text.value.includes(suggestion)) return
  const separator = text.value.trim() ? '\n' : ''
  text.value = `${text.value.trimEnd()}${separator}${suggestion}`
}

// Planning and revising the week with the local coach helper: the two prompt dialogs and the
// background jobs they start. `onPlanned` runs after the coach saved a new week.
export const usePlanCoach = ({ api, flashMessage, selectedPlan, load, onPlanned }) => {
  const planningWithCoach = ref(false)
  const coachPlanningStage = ref('')
  const coachBriefOpen = ref(false)
  const coachPlanningBrief = ref('')
  const coachFeedbackOpen = ref(false)
  const coachPlanFeedback = ref('')
  const isLocalCoachHost = computed(() => {
    if (typeof window === 'undefined') return false
    return localCoachHostnames.has(window.location.hostname.toLowerCase())
  })
  let viewActive = true
  onBeforeUnmount(() => { viewActive = false })

  const openCoachPlanningBrief = () => {
    if (!isLocalCoachHost.value || planningWithCoach.value) return
    coachBriefOpen.value = true
  }
  const closeCoachPlanningBrief = () => {
    if (planningWithCoach.value) return
    coachBriefOpen.value = false
  }
  const addCoachBriefSuggestion = (suggestion) => appendSuggestion(coachPlanningBrief, suggestion)

  const openCoachPlanFeedback = () => {
    if (!isLocalCoachHost.value || planningWithCoach.value || !selectedPlan.value) return
    coachFeedbackOpen.value = true
  }
  const closeCoachPlanFeedback = () => {
    if (planningWithCoach.value) return
    coachFeedbackOpen.value = false
  }
  const addCoachFeedbackSuggestion = (suggestion) => appendSuggestion(coachPlanFeedback, suggestion)

  // Starts a coach job, polls it until it finishes, and reports the outcome in the flash banner.
  const runCoachJob = async ({ stage, started: startedFlash, start, poll, pollingStage, failed, timedOut, failedTitle, failedDetail, onSucceeded }) => {
    planningWithCoach.value = true
    coachPlanningStage.value = stage
    flashMessage.value = { type: 'success', ...startedFlash }
    try {
      const started = await start()
      const jobId = started.data.job_id
      const deadline = Date.now() + (15 * 60 * 1000)
      while (viewActive && Date.now() < deadline) {
        await wait(1800)
        const result = await poll(jobId)
        const job = result.data
        coachPlanningStage.value = job.message || pollingStage
        if (job.status === 'failed') throw new Error(job.message || failed)
        if (job.status === 'succeeded') {
          await onSucceeded(job)
          return
        }
      }
      if (viewActive) throw new Error(timedOut)
    } catch (error) {
      if (!viewActive) return
      const helperUnavailable = Boolean(error?.request && !error?.response)
      flashMessage.value = {
        type: 'error',
        title: helperUnavailable ? 'Local coach helper is not running' : failedTitle,
        detail: helperUnavailable
          ? 'Restart the dashboard with its normal start command, then try again.'
          : (error?.response?.data?.detail || error?.message || failedDetail),
      }
    } finally {
      planningWithCoach.value = false
      coachPlanningStage.value = ''
    }
  }

  const planCurrentWeekWithCoach = async () => {
    if (!isLocalCoachHost.value || planningWithCoach.value) return
    const weekStart = format(startOfWeek(new Date(), { weekStartsOn: 1 }), 'yyyy-MM-dd')
    const planningBrief = coachPlanningBrief.value.trim()
    coachBriefOpen.value = false
    await runCoachJob({
      stage: 'Starting the coach…',
      started: {
        title: 'The coach is planning this week',
        detail: 'You can stay on this page. The plan will refresh automatically when it is saved.',
      },
      start: () => api.startCoachWeeklyPlan({ week_start: weekStart, planning_brief: planningBrief }),
      poll: (jobId) => api.getCoachWeeklyPlanJob(jobId),
      pollingStage: 'The coach is planning…',
      failed: 'The coach could not create the weekly plan.',
      timedOut: 'Planning timed out after 15 minutes.',
      failedTitle: 'The coach could not create the plan',
      failedDetail: 'The weekly planning request failed.',
      onSucceeded: async (job) => {
        onPlanned(weekStart)
        await load()
        flashMessage.value = {
          type: 'success',
          title: 'Weekly plan saved by the coach',
          detail: job.summary || 'The current plan has been refreshed. Use Refine with the coach if you want anything changed.',
        }
      },
    })
  }

  const reviseCurrentPlanWithCoach = async () => {
    if (!isLocalCoachHost.value || planningWithCoach.value || !selectedPlan.value) return
    const feedback = coachPlanFeedback.value.trim()
    if (!feedback) return
    const weekStart = selectedPlan.value.week_start
    coachFeedbackOpen.value = false
    await runCoachJob({
      stage: 'Sending plan feedback to the coach…',
      started: {
        title: 'The coach is revising the plan',
        detail: 'The saved plan will refresh automatically after the revision is complete.',
      },
      start: () => api.startCoachWeeklyPlanRevision({ week_start: weekStart, feedback }),
      poll: (jobId) => api.getCoachWeeklyPlanRevisionJob(jobId),
      pollingStage: 'The coach is revising the plan…',
      failed: 'The coach could not revise the weekly plan.',
      timedOut: 'Revision timed out after 15 minutes.',
      failedTitle: 'The coach could not revise the plan',
      failedDetail: 'The weekly plan revision failed.',
      onSucceeded: async (job) => {
        coachPlanFeedback.value = ''
        await load()
        flashMessage.value = {
          type: 'success',
          title: 'Plan revised from your feedback',
          detail: job.summary || 'The current plan has been refreshed.',
        }
      },
    })
  }

  return {
    planningWithCoach,
    coachPlanningStage,
    coachBriefOpen,
    coachPlanningBrief,
    coachFeedbackOpen,
    coachPlanFeedback,
    isLocalCoachHost,
    openCoachPlanningBrief,
    closeCoachPlanningBrief,
    addCoachBriefSuggestion,
    openCoachPlanFeedback,
    closeCoachPlanFeedback,
    addCoachFeedbackSuggestion,
    planCurrentWeekWithCoach,
    reviseCurrentPlanWithCoach,
  }
}
