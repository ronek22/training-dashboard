import { mkdir, rm, writeFile } from 'node:fs/promises'
import { basename, dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

// The visual assets and their manifest metadata are pinned so this catalog can
// be regenerated without silently changing artwork or attribution.
export const SOURCE_REVISION = 'aac599224bb9780305239607ef98540b7e0ce389'
export const SOURCE_REPOSITORY = 'https://github.com/bryllim/workout-guide'
const SOURCE_RAW_ROOT = `https://raw.githubusercontent.com/bryllim/workout-guide/${SOURCE_REVISION}`
const SOURCE_LICENSE_URL = 'https://creativecommons.org/licenses/by-sa/4.0/'

// The upstream package has exact equipment and movement variants for most of
// the starter catalog. Entries intentionally omitted here remain unsupported
// when only a different stance, grip, or equipment variant exists.
const GUIDE_DEFINITIONS = [
  {
    slug: 'bench-press', name: 'Barbell Bench Press', aliases: ['Barbell Bench Press', 'Bench Press'],
    instructionId: 'Barbell_Bench_Press_-_Medium_Grip',
  },
  {
    slug: 'dumbbell-bench-press', name: 'Dumbbell Bench Press', aliases: ['Dumbbell Bench Press', 'Flat Dumbbell Bench Press'],
    instructionId: 'Dumbbell_Bench_Press',
  },
  {
    slug: 'push-up', name: 'Push-up', aliases: ['Push-up', 'Push Up', 'Pushups', 'Push-Ups'],
    instructionId: 'Pushups',
  },
  {
    slug: 'cable-fly', name: 'Cable Chest Fly', aliases: ['Cable Chest Fly', 'Cable Fly', 'Cable Flye'],
    instructionId: 'Cable_Crossover',
  },
  {
    slug: 'lateral-raise', name: 'Dumbbell Lateral Raise', aliases: ['Dumbbell Lateral Raise', 'Lateral Raise', 'Side Lateral Raise'],
    instructionId: 'Side_Lateral_Raise',
  },
  {
    slug: 'face-pull', name: 'Cable Face Pull', aliases: ['Cable Face Pull', 'Face Pull', 'Face Pull (Cable)'],
    instructionId: 'Face_Pull',
  },
  {
    slug: 'tricep-pushdown', name: 'Cable Triceps Pushdown', aliases: ['Cable Triceps Pushdown', 'Triceps Pushdown', 'Tricep Pushdown'],
    instructionId: 'Triceps_Pushdown',
  },
  {
    slug: 'dumbbell-overhead-tricep-extension', name: 'Dumbbell Overhead Tricep Extension', aliases: ['Dumbbell Overhead Tricep Extension', 'Dumbbell Overhead Triceps Extension'],
  },
  {
    slug: 'close-grip-bench-press', name: 'Close-Grip Bench Press', aliases: ['Close-Grip Bench Press', 'Close Grip Bench Press'],
    instructionId: 'Close-Grip_Barbell_Bench_Press',
  },
  {
    slug: 'bicep-curl', name: 'Dumbbell Biceps Curl', aliases: ['Dumbbell Biceps Curl', 'Dumbbell Bicep Curl', 'Dumbbell Curl', 'Bicep Curl'],
    instructionId: 'Dumbbell_Bicep_Curl',
  },
  {
    slug: 'hammer-curl', name: 'Dumbbell Hammer Curl', aliases: ['Dumbbell Hammer Curl', 'Dumbbell Hammer Curls', 'Hammer Curl', 'Hammer Curls'],
    instructionId: 'Hammer_Curls',
  },
  {
    slug: 'wrist-curl', name: 'Barbell Wrist Curl', aliases: ['Barbell Wrist Curl', 'Wrist Curl'],
  },
  {
    slug: 'farmer-carry', name: 'Farmer Carry', aliases: ['Farmer Carry', "Farmer's Carry", "Farmer's Walk", 'Farmers Walk'],
    instructionId: 'Farmers_Walk',
  },
  {
    slug: 'seated-row', name: 'Seated Cable Row', aliases: ['Seated Cable Row', 'Seated Cable Rows', 'Cable Row (Seated)'],
    instructionId: 'Seated_Cable_Rows',
  },
  {
    slug: 'dumbbell-bent-over-row', name: 'Dumbbell Bent-Over Row', aliases: ['Dumbbell Bent-Over Row', 'Bent Over Two-Dumbbell Row'],
    instructionId: 'Bent_Over_Two-Dumbbell_Row',
  },
  {
    slug: 'one-arm-dumbbell-row', name: 'One-Arm Dumbbell Row', aliases: ['One-Arm Dumbbell Row'],
    instructionId: 'One-Arm_Dumbbell_Row',
  },
  {
    slug: 'lat-pulldown', name: 'Lat Pulldown', aliases: ['Lat Pulldown'],
  },
  {
    slug: 'pull-up', name: 'Pull-up', aliases: ['Pull-up', 'Pull Up'],
  },
  {
    slug: 'dumbbell-shrug', name: 'Dumbbell Shrug', aliases: ['Dumbbell Shrug', 'Dumbbell Shrugs'],
    instructionId: 'Dumbbell_Shrug',
  },
  {
    slug: 'back-extension', name: 'Back Extension', aliases: ['Back Extension', 'Back Extensions', 'Hyperextension', 'Hyperextensions'],
    instructionId: 'Hyperextensions_Back_Extensions',
  },
  {
    slug: 'squat', name: 'Barbell Squat', aliases: ['Barbell Squat'],
    instructionId: 'Barbell_Squat',
  },
  {
    slug: 'goblet-squat', name: 'Goblet Squat', aliases: ['Goblet Squat'],
    instructionId: 'Goblet_Squat',
  },
  {
    slug: 'leg-press', name: 'Leg Press', aliases: ['Leg Press', 'Leg Press Machine'],
    instructionId: 'Leg_Press',
  },
  {
    slug: 'leg-extension', name: 'Leg Extension', aliases: ['Leg Extension', 'Leg Extensions', 'Machine Leg Extension'],
    instructionId: 'Leg_Extensions',
  },
  {
    slug: 'hip-adduction-machine', name: 'Hip Adduction (Machine)', aliases: ['Hip Adduction', 'Hip Adduction Machine', 'Machine Hip Adduction'],
  },
  {
    slug: 'reverse-lunge', name: 'Reverse Lunge', aliases: ['Reverse Lunge', 'Dumbbell Reverse Lunge'],
  },
  {
    slug: 'hip-thrust', name: 'Barbell Hip Thrust', aliases: ['Barbell Hip Thrust', 'Hip Thrust', 'Hip Thrust (Barbell)'],
    instructionId: 'Barbell_Hip_Thrust',
  },
  {
    slug: 'glute-bridge', name: 'Glute Bridge', aliases: ['Glute Bridge', 'Butt Lift (Bridge)'],
    instructionId: 'Butt_Lift_Bridge',
  },
  {
    slug: 'romanian-deadlift', name: 'Romanian Deadlift', aliases: ['Romanian Deadlift', 'Romanian Deadlift (Barbell)'],
    instructionId: 'Romanian_Deadlift',
  },
  {
    slug: 'seated-leg-curl', name: 'Seated Leg Curl', aliases: ['Seated Leg Curl', 'Seated Leg Curls'],
    instructionId: 'Seated_Leg_Curl',
  },
  {
    slug: 'standing-calf-raise', name: 'Standing Calf Raise', aliases: ['Standing Calf Raise', 'Standing Calf Raises'],
    instructionId: 'Standing_Calf_Raises',
  },
  {
    slug: 'seated-calf-raise', name: 'Seated Calf Raise', aliases: ['Seated Calf Raise', 'Seated Calf Raises'],
    instructionId: 'Seated_Calf_Raise',
  },
  {
    slug: 'plank', name: 'Plank', aliases: ['Plank', 'Front Plank'],
    instructionId: 'Plank',
  },
  {
    slug: 'dead-bug', name: 'Dead Bug', aliases: ['Dead Bug', 'Deadbug'],
    instructionId: 'Dead_Bug',
  },
  {
    slug: 'cable-crunch', name: 'Cable Crunch', aliases: ['Cable Crunch'],
    instructionId: 'Cable_Crunch',
  },
  {
    slug: 'side-plank', name: 'Side Plank', aliases: ['Side Plank'],
  },
  {
    slug: 'russian-twist', name: 'Russian Twist', aliases: ['Russian Twist', 'Russian Twists'],
    instructionId: 'Russian_Twist',
  },
]

const rootDirectory = dirname(fileURLToPath(import.meta.url))
const catalogPath = join(rootDirectory, '..', 'frontend', 'src', 'activity-detail', 'exercise-guides.json')
const publicDirectory = join(rootDirectory, '..', 'frontend', 'public', 'exercise-guides')

const responseJson = async (url) => {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`Could not fetch ${url}: ${response.status} ${response.statusText}`)
  return response.json()
}

const responseText = async (url) => {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`Could not fetch ${url}: ${response.status} ${response.statusText}`)
  return response.text()
}

const responseBytes = async (url) => {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`Could not fetch ${url}: ${response.status} ${response.statusText}`)
  return Buffer.from(await response.arrayBuffer())
}

const [manifest, instructionData] = await Promise.all([
  responseJson(`${SOURCE_RAW_ROOT}/packages/workout-guide/manifest.json`),
  responseJson('https://raw.githubusercontent.com/yuhonas/free-exercise-db/a859101d633a01c4a1a920d6a8ce41dabba0705f/dist/exercises.json'),
])
const manifestBySlug = new Map(manifest.map(exercise => [exercise.slug, exercise]))
const instructionById = new Map(instructionData.map(exercise => [exercise.id, exercise]))
const missingSlugs = GUIDE_DEFINITIONS.filter(definition => !manifestBySlug.has(definition.slug)).map(definition => definition.slug)
if (missingSlugs.length) throw new Error(`Missing pinned workout-guide slugs: ${missingSlugs.join(', ')}`)

const fallbackInstructions = name => [
  `Use the three illustrated frames to review the starting position, movement, and finish for ${name}.`,
]

const guides = GUIDE_DEFINITIONS.map(definition => {
  const exercise = manifestBySlug.get(definition.slug)
  const instructions = definition.instructionId
    ? instructionById.get(definition.instructionId)?.instructions
    : null
  const imagePaths = exercise.frames.map(frame => frame.path)
  return {
    id: exercise.slug,
    name: definition.name,
    sourceName: exercise.name,
    images: imagePaths.map(imagePath => `/${imagePath.replace(/^assets\//, 'exercise-guides/')}`),
    instructions: instructions?.length ? instructions : fallbackInstructions(definition.name),
    equipment: exercise.equipment,
    primaryMuscles: [exercise.primaryMuscle],
    sourceUrl: `${SOURCE_REPOSITORY}/blob/${SOURCE_REVISION}/packages/workout-guide/assets/${definition.slug}/frame-1.svg`,
    sourceLabel: 'Workout Guide by Bryl Lim; original pose artwork from Everkinetic',
    attribution: exercise.attribution,
    licenseUrl: SOURCE_LICENSE_URL,
    frameAttribution: exercise.frames.map(frame => ({ index: frame.index, attribution: frame.attribution })),
    instructionSourceUrl: definition.instructionId
      ? `https://github.com/yuhonas/free-exercise-db/blob/a859101d633a01c4a1a920d6a8ce41dabba0705f/exercises/${definition.instructionId}.json`
      : null,
    aliases: [...new Set([exercise.name, definition.name, ...definition.aliases])],
  }
})

const payload = {
  source: {
    name: 'workout-guide',
    sourceLabel: 'Workout Guide by Bryl Lim; original pose artwork from Everkinetic',
    repository: SOURCE_REPOSITORY,
    revision: SOURCE_REVISION,
    license: 'CC BY-SA 4.0',
    licenseUrl: SOURCE_LICENSE_URL,
    manifestUrl: `${SOURCE_RAW_ROOT}/packages/workout-guide/manifest.json`,
    attribution: 'Visual assets by Bryl Lim. Original pose artwork is from Everkinetic. See the vendored ATTRIBUTION.md and LICENSE-ASSETS files for the complete attribution and license terms.',
  },
  instructionSource: {
    name: 'free-exercise-db',
    repository: 'https://github.com/yuhonas/free-exercise-db',
    revision: 'a859101d633a01c4a1a920d6a8ce41dabba0705f',
    license: 'Unlicense',
    licenseUrl: 'https://github.com/yuhonas/free-exercise-db/blob/a859101d633a01c4a1a920d6a8ce41dabba0705f/LICENSE.md',
  },
  guides,
}

await rm(publicDirectory, { recursive: true, force: true })
await mkdir(publicDirectory, { recursive: true })
for (const guide of guides) {
  const exercise = manifestBySlug.get(guide.id)
  const exerciseDirectory = join(publicDirectory, guide.id)
  await mkdir(exerciseDirectory, { recursive: true })
  for (const imagePath of exercise.frames.map(frame => frame.path)) {
    await writeFile(join(exerciseDirectory, basename(imagePath)), await responseBytes(`${SOURCE_RAW_ROOT}/packages/workout-guide/${imagePath}`))
  }
}

for (const fileName of ['ATTRIBUTION.md', 'LICENSE-ASSETS', 'LICENSES.md']) {
  await writeFile(join(publicDirectory, fileName), await responseText(`${SOURCE_RAW_ROOT}/packages/workout-guide/${fileName}`))
}
await writeFile(join(publicDirectory, 'README.md'), `# Exercise guide attribution\n\nThe local SVG artwork is vendored from [Workout Guide](${SOURCE_REPOSITORY}) at revision [${SOURCE_REVISION}](${SOURCE_REPOSITORY}/tree/${SOURCE_REVISION}). The visual assets are licensed under [CC BY-SA 4.0](${SOURCE_LICENSE_URL}). See [ATTRIBUTION.md](./ATTRIBUTION.md), [LICENSE-ASSETS](./LICENSE-ASSETS), and [LICENSES.md](./LICENSES.md) for the upstream attribution and license terms.\n\nThe step instructions in the catalog identify their separate source when they come from [free-exercise-db](https://github.com/yuhonas/free-exercise-db).\n`)
await writeFile(catalogPath, `${JSON.stringify(payload, null, 2)}\n`)

console.log(`Wrote ${guides.length} guides and ${guides.reduce((count, guide) => count + guide.images.length, 0)} SVG frames from ${SOURCE_REVISION}.`)
