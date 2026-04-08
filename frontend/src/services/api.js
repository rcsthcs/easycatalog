const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'
const DETAILS_CACHE_KEY = 'smart-catalog:details-cache:v2'
const DETAILS_CACHE_TTL_MS = 30 * 60 * 1000
const DETAILS_CACHE_LIMIT = 120

const safeParse = (rawValue) => {
  try {
    return JSON.parse(rawValue)
  } catch {
    return null
  }
}

const readDetailsCache = () => {
  const raw = sessionStorage.getItem(DETAILS_CACHE_KEY)
  if (!raw) {
    return {}
  }

  const parsed = safeParse(raw)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return {}
  }

  return parsed
}

const writeDetailsCache = (cache) => {
  try {
    sessionStorage.setItem(DETAILS_CACHE_KEY, JSON.stringify(cache))
  } catch {
    // Ignore storage quota errors.
  }
}

const pruneDetailsCache = (cache) => {
  const now = Date.now()
  const validEntries = Object.entries(cache)
    .filter(([, entry]) => {
      if (!entry || typeof entry !== 'object') {
        return false
      }

      const savedAt = Number(entry.savedAt || 0)
      if (!savedAt || now - savedAt > DETAILS_CACHE_TTL_MS) {
        return false
      }

      return Boolean(entry.payload)
    })
    .sort((a, b) => Number(b[1].savedAt || 0) - Number(a[1].savedAt || 0))
    .slice(0, DETAILS_CACHE_LIMIT)

  return Object.fromEntries(validEntries)
}

const detailsCacheKey = (source, productUrl) => `${source}::${productUrl}`

const getCachedDetails = (source, productUrl) => {
  if (!source || !productUrl) {
    return null
  }

  const key = detailsCacheKey(source, productUrl)
  const cache = pruneDetailsCache(readDetailsCache())
  const entry = cache[key]
  if (!entry || !entry.payload) {
    writeDetailsCache(cache)
    return null
  }

  writeDetailsCache(cache)
  return entry.payload
}

const putCachedDetails = (source, productUrl, payload) => {
  if (!source || !productUrl || !payload) {
    return
  }

  const key = detailsCacheKey(source, productUrl)
  const cache = pruneDetailsCache(readDetailsCache())
  cache[key] = {
    savedAt: Date.now(),
    payload,
  }
  writeDetailsCache(pruneDetailsCache(cache))
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options)
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `HTTP ${response.status}`)
  }
  return response.json()
}

export const api = {
  search(query) {
    return request(`/search?query=${encodeURIComponent(query)}`)
  },
  getCachedProductDetails(source, productUrl) {
    return getCachedDetails(source, productUrl)
  },
  productDetails(source, productUrl, options = {}) {
    if (!options.force) {
      const cached = getCachedDetails(source, productUrl)
      if (cached) {
        return Promise.resolve(cached)
      }
    }

    return request(
      `/product-details?source=${encodeURIComponent(source)}&product_url=${encodeURIComponent(productUrl)}`,
    ).then((payload) => {
      putCachedDetails(source, productUrl, payload)
      return payload
    })
  },
  uploadProxiesText(proxiesText) {
    return request('/proxies/text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ proxies_text: proxiesText }),
    })
  },
  uploadProxiesFile(file) {
    const fd = new FormData()
    fd.append('file', file)
    return request('/proxies/file', {
      method: 'POST',
      body: fd,
    })
  },
  toggleProxy(enabled) {
    return request('/proxies/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    })
  },
  proxyStatus() {
    return request('/proxies/status')
  },
  proxyErrors() {
    return request('/proxies/errors?limit=20')
  },
}
