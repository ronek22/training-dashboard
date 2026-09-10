import test from 'node:test'
import assert from 'node:assert/strict'
import { classifyExercise, summarizeMuscles, MUSCLES } from '../src/activity-detail/muscles.mjs'

test('specific lower-body and shoulder variants take precedence over generic names', () => {
  for (const [name, expected] of [
    ['Seated Leg Curl', 'hamstrings'], ['Leg Press', 'quads'], ['Leg Press Calf Raise', 'calves'],
    ['Dumbbell Romanian Deadlift', 'hamstrings'], ['Cable Reverse Fly', 'shoulders'],
    ['Hanging Leg Raise', 'abs'], ['Barbell Upright Row', 'shoulders'], ['Dumbbell Rear Delt Raise', 'shoulders'], ['Dumbbell Skullcrusher', 'triceps'], ['Reverse Wrist Curl', 'forearms'],
    ['Close-Grip Bench Press', 'triceps'], ['Barbell Bench Press', 'chest'],
    ['Lat Pull-Down', 'lats'], ['Pullup', 'lats'], ['Machine Hip Adduction', 'adductors'],
  ]) assert.equal(classifyExercise(name)?.primary[0], expected, name)
})

test('rear-delt raises include upper-back support and skullcrushers target triceps', () => {
  const rearDelt = classifyExercise('Dumbbell Rear Delt Raise')
  const skullcrusher = classifyExercise('Dumbbell Skullcrusher')
  assert.deepEqual(rearDelt, { primary: ['shoulders'], secondary: ['upper_back'] })
  assert.deepEqual(skullcrusher, { primary: ['triceps'], secondary: [] })
})
test('unknown and composite exercises are not assigned invented muscle groups', () => {
  for (const name of ['', 'My custom movement', 'Rowing Machine', 'Squat to Press', 'Clean and Press', 'Chest Stretch', 'Surprise']) {
    assert.equal(classifyExercise(name), null, name)
  }
})
test('counts working sets including bodyweight, excludes warm-ups and incomplete sets', () => {
  const summary = summarizeMuscles([
    { exercise_name: 'Push-up', sets: [{ is_warmup: true }, { reps: 10, weight_kg: null }, { status: 'pending' }, { status: 'completed', reps: 8 }] },
    { exercise_name: 'Triceps Extension', sets: [{ reps: 10 }] },
    { exercise_name: 'Custom movement', sets: [{ reps: 8 }] },
    { exercise_name: 'Unknown warmup', sets: [{ set_type: 'warmup' }] },
  ])
  assert.equal(summary.mappedExercises, 2)
  assert.deepEqual(summary.unmapped, ['Custom movement'])
  assert.equal(summary.muscles.find(m => m.key === 'chest').primary, 2)
  assert.equal(summary.muscles.find(m => m.key === 'triceps').primary, 1)
  assert.equal(summary.muscles.find(m => m.key === 'triceps').secondary, 2)
  assert(summary.muscles.every(m => MUSCLES.some(known => known.key === m.key)))
})
test('no exercises or only warmups produces an empty map', () => {
  assert.deepEqual(summarizeMuscles().muscles, [])
  assert.deepEqual(summarizeMuscles([{ exercise_name: 'Squat', sets: [{ is_warmup: true }] }]).muscles, [])
})

test('draft coverage follows planned sets and excludes blank or invalid draft rows', () => {
  const exercises = [
    { exercise_name: 'Bench Press', set_count: 4 },
    { exercise_name: 'Triceps Extension', set_count: 2 },
    { exercise_name: '', set_count: 3 },
    { exercise_name: 'Squat', set_count: 0 },
    { exercise_name: 'Squat', set_count: 21 },
    { exercise_name: 'Squat', set_count: 2.5 },
    { exercise_name: 'Squat', set_count: '' },
    { exercise_name: 'Custom movement', set_count: 3 },
  ]
  let summary = summarizeMuscles(exercises, { planned: true })
  assert.deepEqual(summary.unmapped, ['Custom movement'])
  assert.equal(summary.muscles.find(m => m.key === 'chest').primary, 4)
  assert.equal(summary.muscles.find(m => m.key === 'triceps').secondary, 4)
  assert.equal(summary.muscles.find(m => m.key === 'triceps').primary, 2)
  assert(!summary.muscles.some(m => m.key === 'quads'))
  exercises[0].set_count = 6
  summary = summarizeMuscles(exercises, { planned: true })
  assert.equal(summary.muscles.find(m => m.key === 'chest').primary, 6)
  exercises[0].exercise_name = 'Leg Press'
  summary = summarizeMuscles(exercises, { planned: true })
  assert(!summary.muscles.some(m => m.key === 'chest'))
  assert.equal(summary.muscles.find(m => m.key === 'quads').primary, 6)
  assert.deepEqual(summarizeMuscles(exercises).muscles, [])
})
