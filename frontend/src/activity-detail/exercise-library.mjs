import { classifyExercise } from './muscles.mjs'

// Starter movements; personal template exercises are merged in without altering targets.
export const STARTER_EXERCISES = [
  'Barbell Bench Press', 'Dumbbell Bench Press', 'Push-up', 'Cable Chest Fly',
  'Dumbbell Shoulder Press', 'Dumbbell Lateral Raise', 'Cable Face Pull',
  'Cable Triceps Pushdown', 'Dumbbell Triceps Extension', 'Close-Grip Bench Press',
  'Dumbbell Biceps Curl', 'Dumbbell Hammer Curl', 'Barbell Wrist Curl', 'Farmer Carry',
  'Seated Cable Row', 'Dumbbell Row', 'Lat Pulldown', 'Pull-up', 'Dumbbell Shrug',
  'Back Extension', 'Barbell Squat', 'Goblet Squat', 'Leg Press', 'Leg Extension',
  'Reverse Lunge', 'Barbell Hip Thrust', 'Glute Bridge', 'Romanian Deadlift',
  'Seated Leg Curl', 'Hip Adduction', 'Standing Calf Raise', 'Seated Calf Raise',
  'Plank', 'Dead Bug', 'Cable Crunch', 'Side Plank', 'Russian Twist',
].map(exercise_name => ({ exercise_name, source: 'Exercise library' }))

export const exerciseKey = name => String(name || '').trim().toLowerCase().replace(/[-_–—]/g, ' ').replace(/\s+/g, ' ')
export function buildExerciseLibrary(templates = []) {
  const library = new Map(STARTER_EXERCISES.map(exercise => [exerciseKey(exercise.exercise_name), exercise]))
  for (const template of templates) {
    for (const exercise of template.exercises || []) {
      const key = exerciseKey(exercise.exercise_name)
      if (key) library.set(key, { ...exercise, source: 'Your workouts' })
    }
  }
  return [...library.values()].map(exercise => ({ ...exercise, mapping: classifyExercise(exercise.exercise_name) }))
}
export function filterExercises(library, muscle, { query = '', includeSupporting = false } = {}) {
  const search = exerciseKey(query)
  return library.filter(exercise =>
    (exercise.mapping?.primary.includes(muscle) || (includeSupporting && exercise.mapping?.secondary.includes(muscle)))
    && exerciseKey(exercise.exercise_name).includes(search),
  ).sort((a, b) => Number(b.mapping.primary.includes(muscle)) - Number(a.mapping.primary.includes(muscle))
    || Number(b.source === 'Your workouts') - Number(a.source === 'Your workouts')
    || a.exercise_name.localeCompare(b.exercise_name))
}
