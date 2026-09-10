// Conservative name-based estimates, not measured activation or recovery.
// Reference terminology: https://www.nasm.org/workout-exercise-guidance
export const MUSCLES = [
  { key: 'chest', label: 'Chest', focus: 'push' },
  { key: 'shoulders', label: 'Shoulders', focus: 'push' },
  { key: 'triceps', label: 'Triceps', focus: 'push' },
  { key: 'biceps', label: 'Biceps', focus: 'pull' },
  { key: 'forearms', label: 'Forearms', focus: 'pull' },
  { key: 'upper_back', label: 'Upper back', focus: 'pull' },
  { key: 'lats', label: 'Lats', focus: 'pull' },
  { key: 'lower_back', label: 'Lower back', focus: 'pull' },
  { key: 'abs', label: 'Abs', focus: 'core' },
  { key: 'obliques', label: 'Obliques', focus: 'core' },
  { key: 'glutes', label: 'Glutes', focus: 'lower' },
  { key: 'quads', label: 'Quads', focus: 'lower' },
  { key: 'hamstrings', label: 'Hamstrings', focus: 'lower' },
  { key: 'adductors', label: 'Adductors', focus: 'lower' },
  { key: 'calves', label: 'Calves', focus: 'lower' },
]

// Specific variants precede broader movement names to avoid e.g. leg curl → biceps.
const rules = [
  [/\b(?:calf|calves)\b/, ['calves'], []],
  [/\b(?:leg|hamstring) curls?\b|\bnordic\b/, ['hamstrings'], ['calves']],
  [/\bleg extensions?\b/, ['quads'], []],
  [/\b(?:hip|thigh) adductions?\b|\badductor\b/, ['adductors'], []],
  [/\b(?:hip|thigh) abductions?\b|\b(?:glute kickback|hip thrust|glute bridge)\b/, ['glutes'], ['hamstrings']],
  [/\b(?:romanian|stiff leg|straight leg) deadlift\b|\brdl\b|\bgood mornings?\b/, ['hamstrings', 'glutes'], ['lower_back']],
  [/\bdeadlift\b/, ['glutes', 'hamstrings', 'quads'], ['lower_back', 'upper_back', 'forearms']],
  [/\bsquat\b|\blunges?\b|\bleg press\b|\bstep ups?\b/, ['quads', 'glutes'], ['hamstrings', 'adductors']],
  [/\b(?:back|lumbar) extensions?\b|\bhyperextensions?\b/, ['lower_back'], ['glutes', 'hamstrings']],
  [/\b(?:reverse|rear delt) (?:fly|flyes|flys|flies|raises?)\b|\bface pulls?\b/, ['shoulders'], ['upper_back']],
  [/\bshrugs?\b/, ['upper_back'], []],
  [/\bupright rows?\b/, ['shoulders', 'upper_back'], ['biceps']],
  [/\b(?:straight arm|stiff arm) (?:pull ?downs?|pullovers?)\b/, ['lats'], []],
  [/\bpull ?ups?\b|\bchin ?ups?\b|\bpull ?downs?\b/, ['lats'], ['biceps', 'upper_back']],
  [/\brows?\b/, ['upper_back', 'lats'], ['biceps', 'shoulders']],
  [/\b(?:wrist|reverse wrist) curls?\b|\bfarmer(?:s)? (?:walk|carry)\b/, ['forearms'], []],
  [/\b(?:bicep|biceps|hammer|preacher|concentration|reverse|barbell|dumbbell|cable|incline dumbbell) curls?\b/, ['biceps'], ['forearms']],
  [/\b(?:tricep|triceps)\b|\bskull ?crushers?\b|\bpush ?downs?\b|\bclose grip (?:bench )?press\b|\bbench dips?\b/, ['triceps'], []],
  [/\b(?:shoulder|overhead|military|arnold) press\b|\b(?:lateral|front|scaption) raises?\b|\bpike push ups?\b/, ['shoulders'], []],
  [/\bbench press\b|\bchest press\b|\bfloor press\b|\bpush ?ups?\b|\bdips?\b/, ['chest'], ['triceps', 'shoulders']],
  [/\b(?:chest|dumbbell|cable|incline|decline|machine) (?:fly|flyes|flys|flies)\b|\bpec deck\b|\bcable crossover\b/, ['chest'], ['shoulders']],
  [/\bside plank\b|\brussian twist\b|\bwood ?chop\b|\bpallof\b|\bside bends?\b/, ['obliques'], ['abs']],
  [/\bplank\b|\bcrunch(?:es)?\b|\bsit ?ups?\b|\bleg raises?\b|\bknee raises?\b|\bdead bug\b|\bab (?:wheel|rollout)\b/, ['abs'], ['obliques']],
]
export function classifyExercise(name = '') {
  const normalized = String(name).toLowerCase().replace(/[-_–—]/g, ' ').replace(/[^a-z0-9 ]/g, '').replace(/\s+/g, ' ').trim()
  // These composite/cardio/mobility names need their own mappings; don't partially match them.
  if (/\bstretch|\bwarm up\b|\browing\b|\bclean\b|\bsnatch\b|\bto\b|\band\b/.test(normalized)) return null
  const match = rules.find(([pattern]) => pattern.test(normalized))
  return match ? { primary: match[1], secondary: match[2] } : null
}
export const recordedWorkingSets = exercise => (exercise?.sets || []).filter(set =>
  !set.is_warmup && set.set_type !== 'warmup' && (!set.status || set.status === 'completed'),
)
export function plannedSetCount(exercise) {
  if (!String(exercise?.exercise_name || '').trim()) return 0
  const count = Number(exercise.set_count)
  return Number.isInteger(count) && count >= 1 && count <= 20 ? count : 0
}
export function summarizeMuscles(exercises = [], { planned = false } = {}) {
  const counts = new Map()
  const unmapped = []
  let mappedExercises = 0
  for (const exercise of exercises) {
    const sets = planned ? plannedSetCount(exercise) : recordedWorkingSets(exercise).length
    if (!sets) continue
    const mapping = classifyExercise(exercise.exercise_name)
    if (!mapping) { unmapped.push(exercise.exercise_name || 'Unnamed exercise'); continue }
    mappedExercises++
    for (const [role, muscles] of Object.entries(mapping)) {
      for (const key of muscles) {
        const value = counts.get(key) || { ...MUSCLES.find(muscle => muscle.key === key), primary: 0, secondary: 0 }
        value[role] += sets
        counts.set(key, value)
      }
    }
  }
  return {
    muscles: [...counts.values()].sort((a, b) => b.primary - a.primary || b.secondary - a.secondary || a.label.localeCompare(b.label)),
    unmapped,
    mappedExercises,
  }
}
