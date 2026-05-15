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
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Interests</h1>
          <p className="text-sm text-gray-500">Configure research topics for paper matching</p>
        </div>
        <button
          onClick={() => { resetForm(); setShowForm(true) }}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-900 text-white text-sm font-medium rounded-md hover:bg-gray-800"
        >
          <Plus className="w-3.5 h-3.5" />
          Add
        </button>
      </div>

      {/* Form */}
      {showForm && (
        <div className="bg-white border border-gray-200 rounded-lg mb-4">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
            <h2 className="text-sm font-medium text-gray-900">
              {editingId ? 'Edit Interest' : 'New Interest'}
            </h2>
            <button onClick={resetForm} className="p-1 hover:bg-gray-100 rounded">
              <X className="w-4 h-4 text-gray-400" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="p-4 space-y-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Topic *</label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                required
                placeholder="e.g., Large Language Models"
                className="w-full px-3 py-1.5 text-sm border border-gray-200 rounded focus:outline-none focus:border-gray-400"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
                rows={2}
                className="w-full px-3 py-1.5 text-sm border border-gray-200 rounded focus:outline-none focus:border-gray-400 resize-none"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Keywords (comma-separated)</label>
              <input
                type="text"
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="e.g., transformer, attention, fine-tuning"
                className="w-full px-3 py-1.5 text-sm border border-gray-200 rounded focus:outline-none focus:border-gray-400"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Categories</label>
              <div className="flex flex-wrap gap-1.5">
                {CATEGORIES.map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => toggleCategory(cat)}
                    className={`px-2 py-1 text-xs rounded ${
                      categories.includes(cat)
                        ? 'bg-gray-900 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Weight: {weight.toFixed(1)}
              </label>
              <input
                type="range"
                min="0.1"
                max="2.0"
                step="0.1"
                value={weight}
                onChange={(e) => setWeight(parseFloat(e.target.value))}
                className="w-full"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={resetForm}
                className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-3 py-1.5 bg-gray-900 text-white text-sm rounded hover:bg-gray-800"
              >
                {editingId ? 'Update' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Interests Table */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        {loading ? (
          <div className="px-4 py-8 text-center text-sm text-gray-500">Loading...</div>
        ) : interests.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <p className="text-sm text-gray-500">No interests configured</p>
            <p className="text-xs text-gray-400 mt-1">Add interests to get personalized recommendations</p>
          </div>
        ) : (
          <table>
            <thead>
              <tr className="bg-gray-50">
                <th>Topic</th>
                <th>Keywords</th>
                <th className="w-20">Categories</th>
                <th className="w-20">Weight</th>
                <th className="w-16">Status</th>
                <th className="w-20">Actions</th>
              </tr>
            </thead>
            <tbody>
              {interests.map((interest) => (
                <tr key={interest.id}>
                  <td>
                    <p className="text-sm font-medium text-gray-900">{interest.topic}</p>
                    {interest.description && (
                      <p className="text-xs text-gray-500 truncate max-w-xs">{interest.description}</p>
                    )}
                  </td>
                  <td>
                    <div className="flex flex-wrap gap-1">
                      {interest.keywords?.slice(0, 3).map((kw) => (
                        <span key={kw} className="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">
                          {kw}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td>
                    <div className="flex flex-wrap gap-1">
                      {interest.categories?.slice(0, 2).map((cat) => (
                        <span key={cat} className="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">
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
                        className="p-1 hover:bg-gray-100 rounded"
                        title="Edit"
                      >
                        <Edit2 className="w-3.5 h-3.5 text-gray-400" />
                      </button>
                      <button
                        onClick={() => handleDelete(interest.id)}
                        className="p-1 hover:bg-gray-100 rounded"
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
