// Keep the original prose. Convert only a recognized, explicit prescription;
// unknown instructions require review rather than silently guessed reductions.
export function buildStrengthPlanDraft(day, templates = []) {
  const details = day.details || ''
  const reducedLower = /2 easy work sets each of squat or leg press,\s*Romanian deadlift,\s*split squat or leg curl,\s*then calves and core/i.test(details)
  const match = templates.find(template => template.name === day.template_label || template.name === day.title)
  const loadFactor = reducedLower && /70\s*% of (?:usual|normal) load/i.test(details) ? 0.7 : null
  const guidance = [day.target_duration_min ? `Planned duration: ${day.target_duration_min} min.` : '', details].filter(Boolean).join('\n\n')
  const groups = [
    { name: 'Squat', matches: name => /squat|leg press/i.test(name) && !/split|bulgarian/i.test(name), notes: 'Alternative: squat or leg press. 2 easy work sets.' },
    { name: 'Romanian Deadlift', matches: name => /romanian.*deadlift/i.test(name), notes: '2 easy work sets.' },
    { name: 'Split Squat', matches: name => /split squat|leg curl/i.test(name), notes: 'Alternative: split squat or leg curl. 2 easy work sets.' },
    { name: 'Calf Raise', matches: name => /calf|calves/i.test(name), notes: 'Calf work; 2 sets is an editable draft default.' },
    { name: 'Dead Bug', matches: name => /leg raise|crunch|dead bug|sit.?up|ab wheel/i.test(name), notes: 'Core work; 2 sets is an editable draft default.' },
  ]
  const exercises = reducedLower
    ? groups.flatMap((group, index) => {
        const candidates = (match?.exercises || []).filter(exercise => group.matches(exercise.exercise_name))
        // Preserve the template's core movements; choose one of each alternative above.
        const selected = index === 4 ? candidates : candidates.slice(0, 1)
        return (selected.length ? selected : [null]).map(base => ({
          exercise_name: base?.exercise_name || group.name,
          set_count: 2,
          target_reps: base?.target_reps ?? 8,
          target_weight_kg: loadFactor && base?.target_weight_kg != null
            ? Math.floor(base.target_weight_kg * loadFactor * 2) / 2 : null,
          rest_seconds: base?.rest_seconds ?? 90,
          notes: [group.notes, base ? `Reps/rest from saved workout.${loadFactor && base.target_weight_kg != null ? ` Load: 70% of saved ${base.target_weight_kg} kg, rounded down to 0.5 kg.` : ''}` : 'Suggested movement; review reps (8) and rest (90 sec).'].join(' '),
        }))
      })
    : (match?.exercises || []).map(exercise => ({ ...exercise }))
  return {
    id: null,
    oneTime: true,
    name: day.title,
    notes: guidance,
    exercises,
    reviewNotice: reducedLower
      ? 'The first three movements use the prescribed 2 easy work sets. Matching exercises keep reps/rest from your saved workout; other movements use editable defaults of 8 reps and 90 sec rest. Calf/core sets (2) are also editable defaults. ' + (loadFactor ? 'Loads use 70% of saved workout targets where available, rounded down to 0.5 kg; adjust for your usual load and equipment.' : 'Enter loads using the original guidance below.')
      : 'Review the recommendation below and adjust each exercise to match it. ' + (match ? 'Exercises were copied from your saved workout; reductions have not been guessed.' : 'Add the prescribed exercises, sets and reps to this one-time draft.'),
  }
}
