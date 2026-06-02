import { useEffect, useState } from 'react'
import { Plus, Trash2, Edit2, X } from 'lucide-react'
import { interestsApi } from '../../services/api'
import type { Interest, InterestCreate } from '../../types'
import toast from 'react-hot-toast'

const CATEGORIES = [
  'cs.AI', 'cs.CL', 'cs.CV', 'cs.LG', 'cs.MA',
  'cs.NE', 'stat.ML', 'cs.IR', 'cs.RO',
]

export default function InterestsPage() {
  const [interests, setInterests] = useState<Interest[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)

  const [topic, setTopic] = useState('')
  const [description, setDescription] = useState('')
  const [keywords, setKeywords] = useState('')
  const [categories, setCategories] = useState<string[]>([])
  const [weight, setWeight] = useState(1.0)

  useEffect(() => {
    loadInterests()
  }, [])

  const loadInterests = async () => {
    try {
      const data = await interestsApi.list()
      setInterests(data)
    } catch (error) {
      console.error('Failed to load interests:', error)
    } finally {
      setLoading(false)
    }
  }

  const resetForm = () => {
    setTopic('')
    setDescription('')
    setKeywords('')
    setCategories([])
    setWeight(1.0)
    setEditingId(null)
    setShowForm(false)
  }

  const handleEdit = (interest: Interest) => {
    setTopic(interest.topic)
    setDescription(interest.description || '')
    setKeywords(interest.keywords.join(', '))
    setCategories(interest.categories)
    setWeight(interest.weight)
    setEditingId(interest.id)
    setShowForm(true)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    const interestData: InterestCreate = {
      topic,
      description: description || undefined,
      keywords: keywords.split(',').map((k) => k.trim()).filter(Boolean),
      categories,
      weight,
    }

    try {
      if (editingId) {
        await interestsApi.update(editingId, interestData)
        toast.success('Updated')
      } else {
        await interestsApi.create(interestData)
        toast.success('Created')
      }
      resetForm()
      await loadInterests()
    } catch (error) {
      toast.error('Failed to save')
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this interest?')) return
    try {
      await interestsApi.delete(id)
      setInterests((prev) => prev.filter((i) => i.id !== id))
      toast.success('Deleted')
    } catch (error) {
      toast.error('Failed to delete')
    }
  }

  const toggleCategory = (cat: string) => {
    setCategories((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between fade-in stagger-1">
        <div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Interests
          </h1>
          <p className="text-sm text-gray-500 mt-1">Configure research topics for paper matching</p>
        </div>
        <button
          onClick={() => { resetForm(); setShowForm(true) }}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-indigo-500 to-purple-500 text-white text-sm font-medium rounded-2xl hover:from-indigo-600 hover:to-purple-600 transition-all duration-300 hover:scale-105"
        >
          <Plus className="w-4 h-4" />
          Add
        </button>
      </div>

      {/* Form */}
      {showForm && (
        <div className="glass-card fade-in stagger-2">
          <div className="flex items-center justify-between px-6 py-4">
            <h2 className="text-sm font-semibold text-gray-800" style={{ fontFamily: 'Outfit, sans-serif' }}>
              {editingId ? 'Edit Interest' : 'New Interest'}
            </h2>
            <button onClick={resetForm} className="p-1 hover:bg-gray-100 rounded-lg transition-colors duration-300">
              <X className="w-4 h-4 text-gray-400" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="px-6 pb-6 space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Topic *</label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                required
                placeholder="e.g., Large Language Models"
                className="w-full px-4 py-2.5 text-sm bg-white/80 border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 focus:bg-white text-gray-800 placeholder-gray-400 transition-all duration-300"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
                rows={2}
                className="w-full px-4 py-2.5 text-sm bg-white/80 border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 focus:bg-white text-gray-800 placeholder-gray-400 resize-none transition-all duration-300"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Keywords (comma-separated)</label>
              <input
                type="text"
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="e.g., transformer, attention, fine-tuning"
                className="w-full px-4 py-2.5 text-sm bg-white/80 border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 focus:bg-white text-gray-800 placeholder-gray-400 transition-all duration-300"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Categories</label>
              <div className="flex flex-wrap gap-2">
                {CATEGORIES.map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => toggleCategory(cat)}
                    className={`px-3 py-1.5 text-xs rounded-xl transition-all duration-300 ${
                      categories.includes(cat)
                        ? 'bg-indigo-100 text-indigo-700 border border-indigo-200'
                        : 'bg-white/80 text-gray-600 border border-gray-200 hover:bg-indigo-50 hover:text-indigo-700'
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Weight: {weight.toFixed(1)}
              </label>
              <input
                type="range"
                min="0.1"
                max="2.0"
                step="0.1"
                value={weight}
                onChange={(e) => setWeight(parseFloat(e.target.value))}
                className="w-full accent-indigo-500"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={resetForm}
                className="px-4 py-2.5 text-sm bg-white/80 text-gray-700 hover:bg-gray-100 rounded-xl border border-gray-200 transition-all duration-300"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2.5 bg-gradient-to-r from-indigo-500 to-purple-500 text-white text-sm rounded-xl hover:from-indigo-600 hover:to-purple-600 transition-all duration-300"
              >
                {editingId ? 'Update' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Interests Table */}
      <div className="glass-card overflow-hidden fade-in stagger-3">
        {loading ? (
          <div className="px-6 py-8 text-center text-sm text-gray-500">Loading...</div>
        ) : interests.length === 0 ? (
          <div className="px-6 py-8 text-center">
            <p className="text-sm text-gray-500">No interests configured</p>
            <p className="text-xs text-gray-400 mt-1">Add interests to get personalized recommendations</p>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Topic</th>
                <th>Keywords</th>
                <th className="w-20">Categories</th>
                <th className="w-20">Weight</th>
                <th className="w-16">Status</th>
                <th className="w-20">Actions</th>
              </tr>
            </thead>
            <tbody>
              {interests.map((interest, index) => (
                <tr
                  key={interest.id}
                  className="fade-in"
                  style={{ animationDelay: `${(index + 3) * 50}ms` }}
                >
                  <td>
                    <p className="text-sm font-medium text-gray-800">{interest.topic}</p>
                    {interest.description && (
                      <p className="text-xs text-gray-500 truncate max-w-xs">{interest.description}</p>
                    )}
                  </td>
                  <td>
                    <div className="flex flex-wrap gap-1">
                      {interest.keywords?.slice(0, 3).map((kw) => (
                        <span key={kw} className="text-[10px] px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-lg">
                          {kw}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td>
                    <div className="flex flex-wrap gap-1">
                      {interest.categories?.slice(0, 2).map((cat) => (
                        <span key={cat} className="text-[10px] px-2 py-0.5 bg-purple-100 text-purple-700 rounded-lg">
                          {cat}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="text-xs text-gray-600">{interest.weight.toFixed(1)}</td>
                  <td>
                    <span className={`text-xs ${interest.is_active ? 'text-green-600' : 'text-gray-400'}`}>
                      {interest.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleEdit(interest)}
                        className="p-1 hover:bg-indigo-50 rounded-lg transition-colors duration-300"
                        title="Edit"
                      >
                        <Edit2 className="w-3.5 h-3.5 text-gray-400" />
                      </button>
                      <button
                        onClick={() => handleDelete(interest.id)}
                        className="p-1 hover:bg-red-50 rounded-lg transition-colors duration-300"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5 text-gray-400" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
