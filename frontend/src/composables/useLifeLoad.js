import { ref } from 'vue'
import { useApi } from '../stores/api'

// Life-load tags are decoration and planning hints: pages still load if these requests fail.
export const useLifeLoad = () => {
  const api = useApi()
  const tagMeta = ref([])
  const days = ref(new Map())

  const load = async (params) => {
    try {
      const { data } = await api.getLifeLoad(params)
      tagMeta.value = data.tags
      days.value = new Map(data.days.map((day) => [day.date, day]))
    } catch {
      days.value = new Map()
    }
  }

  const setDay = async (date, tags) => {
    const { data } = await api.setLifeLoadDay(date, { tags, note: days.value.get(date)?.note || null })
    const next = new Map(days.value)
    if (data.day) next.set(date, data.day)
    else next.delete(date)
    days.value = next
    return data.day
  }

  const tagsFor = (date) => days.value.get(date)?.tags || []
  const iconsFor = (date) => tagsFor(date).map((key) => tagMeta.value.find((tag) => tag.key === key)).filter(Boolean)

  return { tagMeta, days, load, setDay, tagsFor, iconsFor }
}
