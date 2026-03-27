import { useCallback, useState } from 'react'
import './App.css'

/** 未设置、空串或仅空白时：开发环境走 Vite 代理（同源 /api）；生产默认直连 8090 */
function resolveApiBase(): string {
  const raw = import.meta.env.VITE_API_BASE
  const s = raw == null ? '' : String(raw).trim()
  if (s !== '') {
    return s.replace(/\/$/, '')
  }
  if (import.meta.env.DEV) {
    return ''
  }
  return 'http://127.0.0.1:8090'
}

const apiBase = resolveApiBase()

type Provenance = 'cache' | 'live'

interface SearchHit {
  provenance: Provenance
  job_id: string
  review: Record<string, unknown>
}

interface SearchResponse {
  version: string
  keyword: string
  total: number
  dedupe_dropped: number
  items: SearchHit[]
}

interface RunResponse {
  version: string
  keyword: string
  job_id: string
  summary: Record<string, unknown> | null
  error: string | null
  cache_hits: number
  live_hits: number
  total: number
  dedupe_dropped: number
  items: SearchHit[]
}

function apiUrl(path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`
  if (!apiBase) {
    return p
  }
  return `${apiBase}${p}`
}

async function fetchSearchCache(q: string): Promise<SearchResponse> {
  const qs = new URLSearchParams({ q }).toString()
  const r = await fetch(`${apiUrl('/api/search')}?${qs}`)
  if (!r.ok) {
    throw new Error(`${r.status} ${await r.text()}`)
  }
  return r.json() as Promise<SearchResponse>
}

async function fetchSearchRun(keyword: string): Promise<RunResponse> {
  const r = await fetch(apiUrl('/api/search/run'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keyword }),
  })
  if (!r.ok) {
    throw new Error(`${r.status} ${await r.text()}`)
  }
  return r.json() as Promise<RunResponse>
}

function App() {
  const [keyword, setKeyword] = useState('闷热')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [cacheResult, setCacheResult] = useState<SearchResponse | null>(null)
  const [runResult, setRunResult] = useState<RunResponse | null>(null)
  const [expanded, setExpanded] = useState<number | null>(null)

  const onSearchCache = useCallback(async () => {
    setErr(null)
    setRunResult(null)
    setLoading(true)
    try {
      const data = await fetchSearchCache(keyword.trim())
      setCacheResult(data)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
      setCacheResult(null)
    } finally {
      setLoading(false)
    }
  }, [keyword])

  const onSearchRun = useCallback(async () => {
    setErr(null)
    setCacheResult(null)
    setLoading(true)
    try {
      const data = await fetchSearchRun(keyword.trim())
      setRunResult(data)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
      setRunResult(null)
    } finally {
      setLoading(false)
    }
  }, [keyword])

  const rows: SearchHit[] = runResult?.items?.length
    ? runResult.items
    : cacheResult?.items ?? []

  return (
    <div className="app">
      <header className="header">
        <h1>review_intel 关键词检索</h1>
        <p className="muted">
          后端：GET <code>/api/search</code> · POST <code>/api/search/run</code>（Dummy
          抓取） · 请求基址 {apiBase || '（Vite 代理 /api → :8090）'}
        </p>
      </header>

      <section className="toolbar">
        <label>
          关键词{' '}
          <input
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="例如：闷热、示例归一化"
            size={40}
          />
        </label>
        <button type="button" disabled={loading} onClick={onSearchCache}>
          仅查库
        </button>
        <button type="button" disabled={loading} onClick={onSearchRun}>
          查库并抓取（合并）
        </button>
        {loading && <span className="muted">请求中…</span>}
      </section>

      {err && <div className="error">{err}</div>}

      {cacheResult && (
        <section className="panel">
          <h2>仅查库</h2>
          <p className="stats">
            命中 {cacheResult.total} 条 · 去重丢弃 {cacheResult.dedupe_dropped} · 关键词{' '}
            <strong>{cacheResult.keyword}</strong>
          </p>
        </section>
      )}

      {runResult && (
        <section className="panel">
          <h2>查库并抓取</h2>
          <p className="stats">
            作业 <code>{runResult.job_id}</code> · 库内 {runResult.cache_hits} · 本次入库{' '}
            {runResult.live_hits} · 合并后 {runResult.total} · 去重丢弃 {runResult.dedupe_dropped}
          </p>
          {runResult.error && <p className="error">{runResult.error}</p>}
          {runResult.summary && (
            <pre className="json">{JSON.stringify(runResult.summary, null, 2)}</pre>
          )}
        </section>
      )}

      {(cacheResult || runResult) && rows.length > 0 && (
        <section className="panel">
          <h2>结果列表</h2>
          <table className="grid">
            <thead>
              <tr>
                <th>#</th>
                <th>来源</th>
                <th>job_id</th>
                <th>正文摘要</th>
                <th>发布时间</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((hit, i) => {
                const rev = hit.review as {
                  review_text?: string
                  publish_time?: string
                  extra_meta?: Record<string, unknown>
                }
                const text = rev.review_text ?? ''
                const snippet = text.length > 120 ? `${text.slice(0, 120)}…` : text
                return (
                  <tr key={`${hit.job_id}-${i}-${hit.provenance}`}>
                    <td>{i + 1}</td>
                    <td>
                      <span className={`pill ${hit.provenance}`}>{hit.provenance}</span>
                    </td>
                    <td>
                      <code>{hit.job_id}</code>
                    </td>
                    <td>{snippet}</td>
                    <td>{String(rev.publish_time ?? '')}</td>
                    <td>
                      <button
                        type="button"
                        className="linkish"
                        onClick={() => setExpanded(expanded === i ? null : i)}
                      >
                        {expanded === i ? '收起' : 'extra_meta'}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {expanded !== null && rows[expanded] && (
            <pre className="json">
              {JSON.stringify(
                (rows[expanded].review as { extra_meta?: unknown }).extra_meta ?? {},
                null,
                2,
              )}
            </pre>
          )}
        </section>
      )}
    </div>
  )
}

export default App
