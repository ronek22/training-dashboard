<template>
  <div class="motion-page goals-page">
    <div class="page-head goals-page-head motion-section">
      <div>
        <div class="page-eyebrow">Train · Goals</div>
        <h1 class="page-title">Goals</h1>
        <p class="page-sub">Where you stand, and the one thing worth doing next.</p>
      </div>
      <button class="add-goal-btn" @click="openDialog"><span aria-hidden="true">＋</span> New goal</button>
    </div>

    <div v-if="loading" class="goal-loading motion-section" role="status" aria-live="polite">
      <div v-for="index in 3" :key="index" class="card goal-skeleton"><span></span><span></span><span></span></div>
    </div>
    <div v-else class="goal-sections motion-section">
      <section v-if="goals.length" class="goal-overview" aria-label="Goal overview">
        <div class="goal-overview-copy">
          <span class="overview-kicker">Right now</span>
          <strong>{{ goalOverviewTitle }}</strong>
          <p>{{ goalOverviewCopy }}</p>
        </div>
        <div class="goal-overview-stats">
          <div><strong>{{ goals.length }}</strong><span>In play</span></div>
          <div :class="{ 'is-alert': attentionGoalCount }"><strong>{{ attentionGoalCount }}</strong><span>Need a push</span></div>
          <div :class="{ 'is-alert': reviewItems.length }"><strong>{{ reviewItems.length }}</strong><span>Worth a look</span></div>
        </div>
      </section>

      <section v-if="reviewItems.length || portfolioFlag" class="goal-review" aria-labelledby="goal-review-title">
        <div class="goal-review-head">
          <div>
            <span class="overview-kicker">Check-in</span>
            <h2 id="goal-review-title">{{ reviewTitle }}</h2>
          </div>
          <small>Based on your recent weeks, results and recovery. Nothing changes until you say so.</small>
        </div>
        <article v-if="portfolioFlag" class="goal-review-item goal-portfolio">
          <div class="goal-review-item-top">
            <span class="goal-verdict-chip verdict-warn">Time budget</span>
            <strong>Goals ask for {{ portfolioFlag.implied_weekly_hours }} h a week, you train {{ portfolioFlag.actual_weekly_hours }} h</strong>
            
          </div>
          <p class="goal-review-headline">{{ portfolioFlag.summary }}</p>
        </article>
        <article v-for="item in reviewItems" :key="item.goal_id" class="goal-review-item">
          <div class="goal-review-item-top">
            <span class="goal-verdict-chip" :class="`verdict-${verdictTone(item.review.verdict)}`">{{ item.review.label }}</span>
            <strong>{{ item.title }}</strong>
            
          </div>
          <p class="goal-review-headline">{{ item.review.headline }}</p>
          <ul class="goal-review-evidence">
            <li v-for="line in item.review.evidence" :key="line">{{ line }}</li>
          </ul>
          <div class="goal-review-actions">
            <button
              v-for="(action, index) in reviewActions(item)"
              :key="action.type + index"
              type="button"
              class="goal-review-action"
              :class="{ 'is-primary': index === 0 }"
              :disabled="savingReview"
              @click="openReviewAction(item, action)"
            >
              {{ action.label }}
            </button>
            <button v-if="!hasBuiltInKeep(item)" type="button" class="goal-action" :disabled="savingReview" @click="decideReview(item, 'kept')">Keep as is</button>
            <button type="button" class="goal-action goal-action-quiet" :disabled="savingReview" @click="decideReview(item, 'snoozed')">Snooze 4 weeks</button>
          </div>
        </article>
        <p v-if="reviewMessage" class="goal-message">{{ reviewMessage }}</p>
      </section>

      <div v-if="!goals.length" class="card goal-empty">
        <div class="goal-empty-icon" aria-hidden="true">◎</div>
        <h2>Set your first training target</h2>
        <p>Goals connect your logged activities to a measurable weekly, monthly, or yearly outcome.</p>
        <button class="add-goal-btn" @click="openDialog">Create a goal</button>
      </div>

      <section v-for="section in groupedGoals" :key="section.label" class="goal-section">
        <div class="goal-section-head">
          <div><div class="section-title">{{ section.label }}</div><span>{{ section.items.length }} {{ section.items.length === 1 ? 'goal' : 'goals' }}</span></div>
          <span>{{ sectionWindowLabel(section.key) }}</span>
        </div>
        <div class="goal-grid">
          <GoalCard
            v-for="goal in section.items"
            :key="goal.id"
            :goal="goal"
            :review="reviewFor(goal)"
            :protein-line="proteinLine"
            @edit="openEditDialog"
            @status="openStatusDialog"
          />
        </div>
      </section>

      <section v-if="goalSuggestions.length" class="goal-suggestions" aria-labelledby="goal-suggestions-title">
        <div class="goal-section-head">
          <div>
            <div id="goal-suggestions-title" class="section-title">Ideas for you</div>
            <span>{{ goalSuggestions.length }} {{ goalSuggestions.length === 1 ? 'idea' : 'ideas' }} · nothing is added until you accept</span>
          </div>
        </div>
        <ul class="card goal-suggestion-list">
          <li v-for="suggestion in goalSuggestions" :key="suggestion.key" class="goal-suggestion-row">
            <div class="goal-suggestion-main">
              <span class="goal-suggestion-kind">{{ suggestionSourceLabel(suggestion.source) }} · {{ suggestionPeriodLabel(suggestion.draft?.period_type) }}</span>
              <strong>{{ suggestion.title }}</strong>
              <p>{{ suggestion.rationale }}</p>
              <details v-if="suggestion.evidence?.length || isQualitySuggestion(suggestion)" class="goal-suggestion-why">
                <summary>Why this?</summary>
                <ul>
                  <li v-for="(line, index) in suggestion.evidence" :key="`${suggestion.key}-evidence-${index}`">{{ suggestionEvidenceLine(line) }}</li>
                </ul>
                <router-link v-if="isQualitySuggestion(suggestion)" to="/plan">Browse structured cycling workouts <span aria-hidden="true">↗</span></router-link>
              </details>
            </div>
            <div class="goal-suggestion-actions">
              <button type="button" class="goal-review-action is-primary" :disabled="savingSuggestionKey === suggestion.key" @click="acceptSuggestion(suggestion)">Review &amp; add</button>
              <button type="button" class="goal-action goal-action-quiet" :disabled="savingSuggestionKey === suggestion.key" @click="dismissSuggestion(suggestion)">
                {{ savingSuggestionKey === suggestion.key ? 'Saving...' : 'Not now' }}
              </button>
            </div>
          </li>
        </ul>
        <p v-if="suggestionMessage" class="goal-message">{{ suggestionMessage }}</p>
      </section>

      <section v-if="pastGoals.length" class="card goal-settings-card goal-past-card">
        <button class="goal-settings-toggle" :aria-expanded="pastExpanded" @click="pastExpanded = !pastExpanded">
          <span><strong>Paused &amp; past goals</strong><small>{{ pastGoalsSummary }}</small></span>
          <span aria-hidden="true">{{ pastExpanded ? '−' : '+' }}</span>
        </button>
        <Transition name="expand-fade">
          <ul v-if="pastExpanded" class="goal-past-list">
            <li v-for="goal in pastGoals" :key="goal.id" class="goal-past-row">
              <span class="goal-lifecycle-chip" :class="`lifecycle-${goal.lifecycle_status}`">{{ lifecycleLabel(goal.lifecycle_status) }}</span>
              <div class="goal-past-copy">
                <strong>{{ goal.title }}</strong>
                <small>{{ pastGoalDetail(goal) }}</small>
              </div>
              <button type="button" class="goal-action" :disabled="savingStatus" @click="reactivateGoal(goal)">
                {{ goal.lifecycle_status === 'paused' ? 'Resume' : 'Reactivate' }}
              </button>
            </li>
          </ul>
        </Transition>
      </section>

      <router-link to="/athlete" class="card goal-athlete-link">
        <span><strong>Athlete settings</strong><small>Focus, FTP, restrictions, strength rotation and notes for the coach now live on the Athlete page</small></span>
        <span aria-hidden="true">→</span>
      </router-link>
    </div>

    <Teleport to="body">
    <GoalEditDialog
      v-if="dialogOpen"
      ref="goalDialog"
      v-model:form="form"
      v-model:draft-text="goalDraftText"
      :editing="!!editingGoalId"
      :saving="saving"
      :drafting="draftingGoal"
      :message="message"
      :draft-preview="goalDraftPreview"
      @close="closeDialog"
      @preview="previewGoalDraft"
      @apply="applyGoalDraft"
      @save="saveGoal"
    />

    <div v-if="reviewConfirm" class="goal-dialog-backdrop" @click.self="closeReviewConfirm" @keydown.esc="closeReviewConfirm">
      <div class="goal-dialog card goal-status-dialog" role="dialog" aria-modal="true" aria-labelledby="goal-review-confirm-title">
        <div class="goal-dialog-head">
          <div>
            <div id="goal-review-confirm-title" class="card-title">{{ reviewConfirm.action.label }}</div>
            <div class="goal-dialog-sub">{{ reviewConfirm.item.title }}</div>
          </div>
          <button class="dialog-close" aria-label="Close" @click="closeReviewConfirm">×</button>
        </div>
        <table v-if="reviewConfirm.changes.length" class="goal-change-table">
          <thead><tr><th scope="col"></th><th scope="col">Now</th><th scope="col">After</th></tr></thead>
          <tbody>
            <tr v-for="change in reviewConfirm.changes" :key="change.label">
              <th scope="row">{{ change.label }}</th><td>{{ change.before }}</td><td>{{ change.after }}</td>
            </tr>
          </tbody>
        </table>
        <p v-if="reviewConfirm.action.detail" class="goal-review-detail">{{ reviewConfirm.action.detail }}</p>
        <label v-if="reviewConfirm.action.body?.status" class="goal-draft-field">
          <span>Reason <em>(kept in goal history)</em></span>
          <input v-model="reviewConfirm.reason" class="goal-status-reason" type="text" maxlength="280">
        </label>
        <p v-if="reviewMessage" class="goal-message">{{ reviewMessage }}</p>
        <div class="goal-dialog-actions">
          <button class="dialog-secondary" @click="closeReviewConfirm">Cancel</button>
          <button class="save-btn" :disabled="savingReview" @click="confirmReviewAction">
            {{ savingReview ? 'Saving...' : reviewConfirm.action.method ? 'Apply' : 'Open plan' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="statusDialog" class="goal-dialog-backdrop" @click.self="closeStatusDialog" @keydown.esc="closeStatusDialog">
      <div class="goal-dialog card goal-status-dialog" role="dialog" aria-modal="true" aria-labelledby="goal-status-title">
        <div class="goal-dialog-head">
          <div>
            <div id="goal-status-title" class="card-title">{{ statusDialogCopy.title }}</div>
            <div class="goal-dialog-sub">{{ statusDialogCopy.sub }}</div>
          </div>
          <button class="dialog-close" aria-label="Close" @click="closeStatusDialog">×</button>
        </div>
        <p v-if="statusDialog.goal.commitment === 'anchor' && statusDialog.status !== 'completed'" class="goal-anchor-warning">
          This is an anchor goal{{ statusDialog.goal.purpose ? ` — ${statusDialog.goal.purpose}` : '' }}. Only {{ statusDialog.status === 'paused' ? 'pause' : 'retire' }} it if that purpose no longer applies.
        </p>
        <label class="goal-draft-field">
          <span>Reason <em>(optional, kept in goal history)</em></span>
          <input
            ref="statusReasonInput"
            v-model="statusDialog.reason"
            class="goal-status-reason"
            type="text"
            maxlength="280"
            :placeholder="statusDialogCopy.placeholder"
            @keydown.enter="confirmStatusChange"
          >
        </label>
        <p v-if="statusMessage" class="goal-message">{{ statusMessage }}</p>
        <div class="goal-dialog-actions">
          <button class="dialog-secondary" @click="closeStatusDialog">Cancel</button>
          <button class="save-btn" :disabled="savingStatus" @click="confirmStatusChange">
            {{ savingStatus ? 'Saving...' : statusDialogCopy.confirm }}
          </button>
        </div>
      </div>
    </div>
    </Teleport>

  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { cached, onCacheRefresh, useApi } from '../stores/api'
import GoalCard from '../goals/GoalCard.vue'
import GoalEditDialog from '../goals/GoalEditDialog.vue'
import {
  defaultForm,
  formFromDraft,
  formFromGoal,
  formatShortDate,
  goalPayloadFromForm,
  hasBuiltInKeep,
  isQualitySuggestion,
  lifecycleLabel,
  lifecyclePayloadFromForm,
  pastGoalDetail,
  pastGoalsSummary as summarizePastGoals,
  reviewActions,
  reviewChanges,
  sectionWindowLabel,
  statusDialogCopy as copyForStatusDialog,
  suggestionEvidenceLine,
  suggestionPeriodLabel,
  suggestionSourceLabel,
  verdictTone,
} from '../goals/goal-helpers.mjs'

const api = useApi()
const router = useRouter()
const loading = ref(true)
const saving = ref(false)
const draftingGoal = ref(false)
const message = ref('')
const allGoals = ref([])
const goals = computed(() => allGoals.value.filter((goal) => goal.lifecycle_status === 'active'))
const pastGoals = computed(() =>
  allGoals.value
    .filter((goal) => goal.lifecycle_status !== 'active')
    .sort((left, right) => String(right.status_changed_at || '').localeCompare(String(left.status_changed_at || '')))
)
const pastExpanded = ref(false)
const goalReview = ref(null)
const goalSuggestions = ref([])
const savingSuggestionKey = ref('')
const suggestionMessage = ref('')
const reviewConfirm = ref(null)
const savingReview = ref(false)
const reviewMessage = ref('')
const pendingNextGoal = ref(null)
const editingGoalId = ref(null)
const statusDialog = ref(null)
const statusReasonInput = ref(null)
const savingStatus = ref(false)
const statusMessage = ref('')
const dialogOpen = ref(false)
const goalDraftText = ref('')
const goalDraftPreview = ref(null)
const goalDialog = ref(null)
const form = ref(defaultForm())
const loadGoals = async () => {
  // A background refresh updates the goals in place, without the skeleton.
  loading.value = !allGoals.value.length
  try {
    allGoals.value = (await cached(() => api.getGoals({ limit: 48, include_history: true, include_outcomes: true }))).data
  } finally {
    loading.value = false
  }
  await Promise.all([loadReview(), loadSuggestions()])
}

// The review is a secondary layer: if it fails, the goals page still works.
const loadReview = async () => {
  try {
    goalReview.value = (await cached(api.getGoalReview)).data
  } catch {
    goalReview.value = null
  }
}

const loadSuggestions = async () => {
  try {
    const result = await cached(api.getGoalSuggestions)
    const suggestions = result.data?.suggestions ?? result.data
    goalSuggestions.value = Array.isArray(suggestions) ? suggestions.slice(0, 3) : []
  } catch {
    goalSuggestions.value = []
  }
}

// Protein on lift days backs the strength goal without becoming calorie tracking.
const proteinStatus = ref(null)
const proteinLine = computed(() => {
  const week = proteinStatus.value?.week
  if (!week?.lift_days) return ''
  const target = proteinStatus.value.target_g ? ` (~${proteinStatus.value.target_g} g)` : ''
  return `Protein on lift days this week: ${week.hits}/${week.lift_days}${target}`
})

onCacheRefresh(loadGoals)
onMounted(async () => {
  await loadGoals()
  cached(api.getProteinStatus).then(({ data }) => { proteinStatus.value = data }).catch(() => {})
})

const groupedGoals = computed(() => {
  const groups = [
    { label: 'Weekly', key: 'week' },
    { label: 'Monthly', key: 'month' },
    { label: 'Yearly', key: 'year' },
  ]
  return groups
    .map((group) => ({
      label: group.label,
      key: group.key,
      items: goals.value.filter((goal) => goal.period_type === group.key),
    }))
    .filter((group) => group.items.length)
})
const attentionGoalCount = computed(() => goals.value.filter((goal) => ['behind_pace', 'constrained'].includes(goal.status)).length)
const completedGoalCount = computed(() => goals.value.filter((goal) => goal.status === 'completed').length)
const priorityGoal = computed(() =>
  goals.value.find((goal) => goal.status === 'behind_pace') ||
  goals.value.find((goal) => goal.status === 'constrained') ||
  goals.value.find((goal) => goal.status === 'on_pace') ||
  goals.value[0]
)
const goalOverviewTitle = computed(() => {
  if (attentionGoalCount.value) return `${attentionGoalCount.value} ${attentionGoalCount.value === 1 ? 'goal needs' : 'goals need'} a push this week`
  if (goals.value.length && completedGoalCount.value === goals.value.length) return 'Every target reached. Time to aim higher.'
  return 'You are on track. Keep it rolling.'
})
const goalOverviewCopy = computed(() => {
  const goal = priorityGoal.value
  if (!goal) return ''
  const action = goal.goal_readiness?.what_matters_next?.summary || goal.planning_guidance?.summary || goal.weekly_requirement_summary
  return action ? `${goal.title}: ${action}` : `${goal.title} is the clearest priority right now.`
})
const openDialog = () => {
  message.value = ''
  editingGoalId.value = null
  form.value = defaultForm()
  goalDraftText.value = ''
  goalDraftPreview.value = null
  dialogOpen.value = true
  nextTick(() => goalDialog.value?.focusDraft())
}

const openEditDialog = (goal) => {
  message.value = ''
  editingGoalId.value = goal.id
  form.value = formFromGoal(goal)
  goalDraftText.value = ''
  goalDraftPreview.value = null
  dialogOpen.value = true
}

const reviewByGoal = computed(() => Object.fromEntries((goalReview.value?.goals || []).map((item) => [item.goal_id, item.review])))
const reviewFor = (goal) => reviewByGoal.value[goal.id] || null
const reviewItems = computed(() => (goalReview.value?.goals || []).filter((item) => item.review.needs_attention))
const portfolioFlag = computed(() => (goalReview.value?.portfolio?.status === 'over_committed' ? goalReview.value.portfolio : null))
const reviewTitle = computed(() => {
  const count = reviewItems.value.length
  if (!count) return 'Your goals ask for more time than you train'
  return `${count} ${count === 1 ? 'goal is' : 'goals are'} worth a look`
})

const openReviewAction = (item, action) => {
  reviewMessage.value = ''
  if (action.type === 'create_next') {
    openNextGoalDraft(item, action)
    return
  }
  reviewConfirm.value = { item, action, changes: reviewChanges(item, action), reason: action.body?.reason || '' }
}

const closeReviewConfirm = () => {
  if (savingReview.value) return
  reviewConfirm.value = null
}

const decideReview = async (item, decision) => {
  savingReview.value = true
  reviewMessage.value = ''
  try {
    await api.recordGoalReviewDecision(item.goal_id, { verdict: item.review.verdict, decision })
    await loadReview()
  } catch (error) {
    reviewMessage.value = error?.response?.data?.detail || 'Failed to save the review decision.'
  } finally {
    savingReview.value = false
  }
}

const acceptSuggestion = (suggestion) => {
  suggestionMessage.value = ''
  openNextGoalDraft(
    suggestion,
    { body: suggestion.draft, detail: suggestion.rationale },
    suggestion.key,
  )
}

const dismissSuggestion = async (suggestion) => {
  if (!suggestion?.key || savingSuggestionKey.value) return
  savingSuggestionKey.value = suggestion.key
  suggestionMessage.value = ''
  try {
    await api.recordGoalSuggestionDecision(suggestion.key, { decision: 'dismissed' })
    goalSuggestions.value = goalSuggestions.value.filter((item) => item.key !== suggestion.key)
  } catch (error) {
    suggestionMessage.value = error?.response?.data?.detail || 'Failed to dismiss the suggestion.'
  } finally {
    savingSuggestionKey.value = ''
  }
}

const confirmReviewAction = async () => {
  const { item, action, reason } = reviewConfirm.value || {}
  if (!action || savingReview.value) return
  if (!action.method) {
    await decideReview(item, 'kept')
    reviewConfirm.value = null
    router.push('/plan')
    return
  }
  savingReview.value = true
  reviewMessage.value = ''
  try {
    const body = action.body?.status ? { ...action.body, reason: reason?.trim() || null } : action.body
    await api.applyGoalReviewAction({ ...action, body })
    await api.recordGoalReviewDecision(item.goal_id, { verdict: item.review.verdict, decision: 'applied' })
    reviewConfirm.value = null
    await loadGoals()
  } catch (error) {
    reviewMessage.value = error?.response?.data?.detail || 'Failed to apply the change.'
  } finally {
    savingReview.value = false
  }
}

// Next period's goal opens in the normal editor so its target can be adjusted
// first. A goal that starts in the future is saved paused until its start date.
const openNextGoalDraft = (item, action, suggestionKey = null) => {
  message.value = ''
  editingGoalId.value = null
  goalDraftText.value = ''
  goalDraftPreview.value = null
  const draft = action.body || {}
  form.value = formFromGoal(draft)
  pendingNextGoal.value = { startDate: draft.start_date, detail: action.detail, suggestionKey }
  message.value = action.detail || ''
  dialogOpen.value = true
}

const statusDialogCopy = computed(() => copyForStatusDialog(statusDialog.value))
const pastGoalsSummary = computed(() => summarizePastGoals(pastGoals.value))

const openStatusDialog = (goal, status) => {
  statusMessage.value = ''
  statusDialog.value = { goal, status, reason: '' }
  nextTick(() => statusReasonInput.value?.focus())
}

const closeStatusDialog = () => {
  if (savingStatus.value) return
  statusDialog.value = null
}

const changeGoalStatus = async (goal, status, reason) => {
  savingStatus.value = true
  statusMessage.value = ''
  try {
    await api.setGoalStatus(goal.id, { status, reason: reason?.trim() || null })
    await loadGoals()
    return true
  } catch (error) {
    statusMessage.value = error?.response?.data?.detail || 'Failed to update goal.'
    return false
  } finally {
    savingStatus.value = false
  }
}

const confirmStatusChange = async () => {
  const dialog = statusDialog.value
  if (!dialog || savingStatus.value) return
  if (await changeGoalStatus(dialog.goal, dialog.status, dialog.reason)) statusDialog.value = null
}

const reactivateGoal = (goal) => changeGoalStatus(goal, 'active', null)

const closeDialog = () => {
  if (saving.value) return
  editingGoalId.value = null
  pendingNextGoal.value = null
  dialogOpen.value = false
  form.value = defaultForm()
  goalDraftText.value = ''
  goalDraftPreview.value = null
}

const saveGoal = async () => {
  saving.value = true
  message.value = ''
  suggestionMessage.value = ''
  try {
    const payload = { ...goalPayloadFromForm(form.value), ...lifecyclePayloadFromForm(form.value) }
    const pendingSuggestionKey = pendingNextGoal.value?.suggestionKey
    const scheduledStart = pendingNextGoal.value?.startDate || form.value.start_date
    if (editingGoalId.value) {
      await api.updateGoal(editingGoalId.value, payload)
    } else if (scheduledStart && scheduledStart > new Date().toISOString().slice(0, 10)) {
      const { data } = await api.createGoal({ ...payload, is_active: false, review_on: scheduledStart })
      await api.setGoalStatus(data.id, { status: 'paused', reason: `Starts ${formatShortDate(scheduledStart)}` })
    } else {
      await api.createGoal(payload)
    }
    if (pendingSuggestionKey) {
      try {
        await api.recordGoalSuggestionDecision(pendingSuggestionKey, { decision: 'accepted' })
      } catch {
        suggestionMessage.value = 'Goal saved, but the suggestion decision could not be recorded.'
      }
    }
    pendingNextGoal.value = null
    await loadGoals()
    dialogOpen.value = false
    editingGoalId.value = null
    form.value = defaultForm()
    message.value = 'Goal saved.'
  } catch (error) {
    message.value = error?.response?.data?.detail || 'Failed to save goal.'
  } finally {
    saving.value = false
  }
}

const previewGoalDraft = async () => {
  draftingGoal.value = true
  message.value = ''
  try {
    const result = await api.draftGoal({ text: goalDraftText.value })
    goalDraftPreview.value = result.data
    if (!result.data?.is_supported) {
      message.value = 'Draft needs a simpler measurable phrase.'
    } else if (result.data?.is_ready) {
      message.value = 'Draft parsed. Review it before saving.'
    } else {
      message.value = 'Draft parsed partially. Review the warnings and fill the remaining fields.'
    }
  } catch (error) {
    message.value = error?.response?.data?.detail || 'Failed to draft goal.'
  } finally {
    draftingGoal.value = false
  }
}

const applyGoalDraft = () => {
  if (!goalDraftPreview.value?.goal) return
  form.value = formFromDraft(goalDraftPreview.value)
  message.value = goalDraftPreview.value?.is_ready
    ? 'Draft applied. Review the structured fields and save when ready.'
    : 'Partial draft applied. Finish the missing fields before saving.'
}
</script>

<style scoped src="../goals/Goals.css"></style>
