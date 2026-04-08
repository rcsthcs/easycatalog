import { useEffect, useMemo, useState } from 'react'
import Loader from '../components/Loader'
import ProductCard from '../components/ProductCard'
import ProxyPanel from '../components/ProxyPanel'
import SearchBar from '../components/SearchBar'
import Tabs from '../components/Tabs'
import Toast from '../components/Toast'
import { api } from '../services/api'

const SEARCH_STATE_KEY = 'smart-catalog:search-state:v1'
const SOURCES = ['kaspi', 'wildberries', 'ozon']

const createEmptyResults = () => ({ kaspi: [], wildberries: [], ozon: [] })

const normalizeResults = (raw) => {
  const normalized = createEmptyResults()
  if (!raw || typeof raw !== 'object') {
    return normalized
  }

  SOURCES.forEach((source) => {
    if (Array.isArray(raw[source])) {
      normalized[source] = raw[source]
    }
  })

  return normalized
}

const normalizeSourceErrors = (raw) => {
  if (!raw || typeof raw !== 'object') {
    return {}
  }

  const normalized = {}
  SOURCES.forEach((source) => {
    if (typeof raw[source] === 'string' && raw[source].trim()) {
      normalized[source] = raw[source]
    }
  })
  return normalized
}

const loadSavedState = () => {
  try {
    const raw = sessionStorage.getItem(SEARCH_STATE_KEY)
    if (!raw) {
      return null
    }

    const parsed = JSON.parse(raw)
    const activeTab = SOURCES.includes(parsed.activeTab) ? parsed.activeTab : 'kaspi'

    return {
      query: typeof parsed.query === 'string' ? parsed.query : '',
      activeTab,
      results: normalizeResults(parsed.results),
      sourceErrors: normalizeSourceErrors(parsed.sourceErrors),
    }
  } catch {
    return null
  }
}

export default function SearchPage() {
  const restoredState = useMemo(() => loadSavedState(), [])

  const [query, setQuery] = useState(restoredState?.query || '')
  const [activeTab, setActiveTab] = useState(restoredState?.activeTab || 'kaspi')
  const [results, setResults] = useState(restoredState?.results || createEmptyResults())
  const [sourceErrors, setSourceErrors] = useState(restoredState?.sourceErrors || {})
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState('')

  useEffect(() => {
    const payload = {
      query,
      activeTab,
      results,
      sourceErrors,
    }

    try {
      sessionStorage.setItem(SEARCH_STATE_KEY, JSON.stringify(payload))
    } catch {
      // Ignore storage errors; the page remains usable without persistence.
    }
  }, [query, activeTab, results, sourceErrors])

  const handleSearch = async (event) => {
    event.preventDefault()
    const prepared = query.trim()
    if (prepared.length < 2) {
      return
    }

    setLoading(true)
    setToast('')

    try {
      const payload = await api.search(prepared)
      const nextResults = createEmptyResults()
      const nextErrors = {}
      payload.results.forEach((entry) => {
        nextResults[entry.source] = entry.items.slice(0, 10)
        if (entry.error) {
          nextErrors[entry.source] = entry.error
        }
      })
      setResults(nextResults)
      setSourceErrors(nextErrors)
      setActiveTab('kaspi')
    } catch (error) {
      setToast(`Ошибка поиска: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const activeItems = useMemo(() => results[activeTab] || [], [results, activeTab])

  return (
    <main className="page">
      <section className="hero">
        <h1>Smart Catalog</h1>
        <p>Поиск товаров сразу в Kaspi, Wildberries и Ozon</p>
        <SearchBar value={query} onChange={setQuery} onSubmit={handleSearch} loading={loading} />
      </section>

      <ProxyPanel notify={setToast} />

      <section className="results">
        <div className="results-head">
          <h2>Результаты</h2>
          <p>Первые 10 товаров по каждому источнику</p>
        </div>

        <Tabs activeTab={activeTab} onTabChange={setActiveTab} />

        {sourceErrors[activeTab] && <p className="source-error">Источник вернул ошибку: {sourceErrors[activeTab]}</p>}

        {loading && <Loader text="Собираем данные с маркетплейсов..." />}

        {!loading && activeItems.length === 0 && (
          <p className="empty">Ничего не найдено в этой вкладке. Попробуйте другой запрос.</p>
        )}

        <div className="product-grid">
          {!loading &&
            activeItems.map((item) => (
              <ProductCard
                key={`${item.source}-${item.product_url}`}
                item={item}
              />
            ))}
        </div>
      </section>

      <Toast message={toast} onClose={() => setToast('')} />
    </main>
  )
}
