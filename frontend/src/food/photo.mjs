// Photos are downscaled before upload: enough detail to read a label or judge portions, far smaller to send.
export async function readPhoto(file, maxSide = 1280) {
  if (!file?.type?.startsWith('image/')) return null
  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * scale)
  canvas.height = Math.round(bitmap.height * scale)
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  const url = canvas.toDataURL('image/jpeg', 0.88)
  return { url, media_type: 'image/jpeg', data: url.split(',')[1] }
}
