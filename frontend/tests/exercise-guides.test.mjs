import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  EXERCISE_GUIDE_SOURCE,
  EXERCISE_GUIDES,
  getExerciseGuide,
  normalizeExerciseName,
} from '../src/activity-detail/exercise-guides.mjs'
import { STARTER_EXERCISES } from '../src/activity-detail/exercise-library.mjs'

const projectRoot = join(dirname(fileURLToPath(import.meta.url)), '..')

test('catalog is pinned to the public-domain source and every image is local', () => {
  assert.equal(EXERCISE_GUIDE_SOURCE.name, 'workout-guide')
  assert.match(EXERCISE_GUIDE_SOURCE.revision, /^[0-9a-f]{40}$/)
  assert.equal(EXERCISE_GUIDE_SOURCE.license, 'CC BY-SA 4.0')
  assert.equal(EXERCISE_GUIDES.length, 37)
  for (const guide of EXERCISE_GUIDES) {
    assert(guide.instructions.length > 0, guide.id)
    assert.equal(guide.images.length, 3, guide.id)
    assert.equal(guide.licenseUrl, 'https://creativecommons.org/licenses/by-sa/4.0/')
    assert.equal(guide.frameAttribution.length, 3, guide.id)
    for (const image of guide.images) {
      assert.match(image, /^\/exercise-guides\/.+\/frame-[123]\.svg$/)
      assert(existsSync(join(projectRoot, 'public', image.slice(1))), image)
    }
  }
})

test('normalization is limited to punctuation, separators, and spacing', () => {
  assert.equal(normalizeExerciseName('  Farmer’s-Walk  '), 'farmers walk')
  assert.equal(normalizeExerciseName('Cable_Row (Seated)'), 'cable row seated')
  assert.equal(normalizeExerciseName(''), '')
})

test('explicit aliases resolve common starter and Fitbod names', () => {
  assert.equal(getExerciseGuide('Barbell Bench Press').id, 'bench-press')
  assert.equal(getExerciseGuide('cable chest fly').id, 'cable-fly')
  assert.equal(getExerciseGuide('Dumbbell Biceps Curl').id, 'bicep-curl')
  assert.equal(getExerciseGuide("Farmer's Carry").id, 'farmer-carry')
  assert.equal(getExerciseGuide('Side Plank').id, 'side-plank')
  assert.equal(getExerciseGuide('Wrist Curl').id, 'wrist-curl')
})

test('starter coverage stays conservative and reports only known gaps', () => {
  const covered = STARTER_EXERCISES.filter(exercise => getExerciseGuide(exercise.exercise_name))
  assert.equal(covered.length, 34)
  assert.deepEqual(
    STARTER_EXERCISES.filter(exercise => !getExerciseGuide(exercise.exercise_name)).map(exercise => exercise.exercise_name),
    ['Dumbbell Shoulder Press', 'Dumbbell Triceps Extension', 'Dumbbell Row'],
  )
})

test('equipment and movement variants do not collapse into an unrelated guide', () => {
  assert.equal(getExerciseGuide('Close-Grip Bench Press').id, 'close-grip-bench-press')
  assert.notEqual(getExerciseGuide('Close-Grip Bench Press').id, getExerciseGuide('Barbell Bench Press').id)
  assert.equal(getExerciseGuide('Dumbbell Shoulder Press'), null)
  assert.equal(getExerciseGuide('Dumbbell Triceps Extension'), null)
  assert.equal(getExerciseGuide('Dumbbell Row'), null)
  assert.equal(getExerciseGuide('Dumbbell Bent-Over Row').id, 'dumbbell-bent-over-row')
  assert.equal(getExerciseGuide('One-Arm Dumbbell Row').id, 'one-arm-dumbbell-row')
  assert.notEqual(getExerciseGuide('Dumbbell Bent-Over Row').id, getExerciseGuide('One-Arm Dumbbell Row').id)
  assert.equal(getExerciseGuide('Lat Pulldown').id, 'lat-pulldown')
  assert.equal(getExerciseGuide('Pull-up').id, 'pull-up')
  assert.equal(getExerciseGuide('Hip Adduction').id, 'hip-adduction-machine')
  assert.equal(getExerciseGuide('Unknown exercise'), null)
  assert.equal(getExerciseGuide(null), null)
})

test('returned guides expose only the UI contract and protect catalog arrays', () => {
  const guide = getExerciseGuide('Dead Bug')
  assert.deepEqual(Object.keys(guide).sort(), ['attribution', 'equipment', 'id', 'images', 'instructions', 'licenseUrl', 'name', 'primaryMuscles', 'sourceLabel', 'sourceUrl'].sort())
  assert.equal(guide.sourceLabel, 'Workout Guide by Bryl Lim; original pose artwork from Everkinetic')
  assert.equal(guide.attribution, 'Bryl Lim.')
  guide.images.pop()
  guide.instructions.pop()
  assert.equal(getExerciseGuide('Dead Bug').images.length, 3)
  assert.equal(getExerciseGuide('Dead Bug').instructions.length > 0, true)
})
