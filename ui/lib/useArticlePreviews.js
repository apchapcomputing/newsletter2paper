'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useSelectedPublications } from '../contexts/useSelectedPublications'
import { useNewsletterConfig } from '../contexts/useNewsletterConfig'
import { apiFetch } from './apiFetch'
import { articleWindowKey, articleWindowQuery, toQueryString } from './createFlow'
import logger from '../utils/logger'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const MAX_RETRIES = 3
const RETRY_DELAYS = [500, 1000, 2000] // Exponential backoff

const LOADING = { status: 'loading', articles: [], error: '' }
const EMPTY = { status: 'loaded', articles: [], error: '' }
// Nothing can be asked yet: the issue is not saved, or the publication has no database id.
const WAITING = { status: 'waiting', articles: [], error: '' }

/**
 * Articles that would be printed for each selected publication, for the current article window.
 * Lives above the steps so the Add step's lists and the Print step's front page read one source.
 *
 * The cache is keyed by issue → window → publication id → {status, articles, error}, so switching
 * the window back and forth serves from memory while another paper never sees this one's results.
 */
export function useArticlePreviews() {
    const { selectedPublications } = useSelectedPublications()
    const { articleWindow, frequency, dateFrom, dateTo, currentIssueId } = useNewsletterConfig()
    const [cache, setCache] = useState({})
    const inFlight = useRef(new Set())
    // The newest request for a publication in a bucket wins; an older one that lands later is dropped.
    const generations = useRef({})

    const windowConfig = { articleWindow, frequency, dateFrom, dateTo }
    const windowKey = articleWindowKey(windowConfig)
    const query = articleWindowQuery(windowConfig)
    const bucket = `${currentIssueId || 'unsaved'}|${windowKey}`

    // Callers (a modal that awaited a save, a retry timer) run after the render that created them,
    // so everything fetchFor needs is read from the latest render, not from its closure.
    const live = useRef({})
    live.current = { selectedPublications, currentIssueId, query, bucket, isCustom: !query?.days_back }

    const fetchFor = useCallback(async (pubId, { retryCount = 0, force = false, generation } = {}) => {
        const { currentIssueId: issueId, query: windowQuery, bucket: key, isCustom } = live.current
        if (!issueId || !pubId) {
            logger.log('⚠️ Missing issue ID or publication ID, skipping fetch')
            return
        }
        if (!windowQuery) return // A custom range that is not ready yet

        const flightKey = `${key}:${pubId}`
        if (retryCount === 0 && !force && inFlight.current.has(flightKey)) return
        // A retry belongs to the request that scheduled it; a fresh call starts a new generation.
        const gen = retryCount === 0 ? (generations.current[flightKey] || 0) + 1 : generation
        if (retryCount === 0) generations.current[flightKey] = gen
        else if (generations.current[flightKey] !== gen) return
        inFlight.current.add(flightKey)

        const current = () => generations.current[flightKey] === gen
        const setEntry = (entry) =>
            setCache(prev => ({ ...prev, [key]: { ...prev[key], [pubId]: entry } }))

        setEntry(LOADING)

        try {
            const response = await apiFetch(
                `/api/articles/preview/${issueId}?${toQueryString(windowQuery)}&publication_id=${pubId}`
            )

            if (!response.ok) {
                const errorText = await response.text()
                logger.error(`Failed to fetch previews (${response.status}):`, errorText)
                throw new Error(`Failed to fetch article previews: ${response.status} ${response.statusText}`)
            }

            const result = await response.json()
            if (!current()) return // Superseded by a newer request

            if (result.success && result.data) {
                const articles = result.data.articles_by_publication?.[pubId] || []
                const pubExists = live.current.selectedPublications.some(p => p.id === pubId)

                // Retry for preset windows only: for a custom range, 0 articles is a valid answer.
                if (articles.length === 0 && pubExists && retryCount < MAX_RETRIES && !isCustom) {
                    logger.log(`🔄 Retry ${retryCount + 1}/${MAX_RETRIES} for publication ${pubId} after ${RETRY_DELAYS[retryCount]}ms`)
                    setTimeout(() => fetchFor(pubId, { retryCount: retryCount + 1, generation: gen }), RETRY_DELAYS[retryCount])
                    return
                }

                setEntry({ status: 'loaded', articles, error: '' })
                logger.log(`✅ Loaded ${articles.length} articles for "${key}" / ${pubId}`)
            } else {
                setEntry(EMPTY)
            }
            inFlight.current.delete(flightKey)
        } catch (error) {
            if (!current()) return
            logger.error(`Error fetching articles for publication ${pubId}:`, error)
            setEntry({ status: 'error', articles: [], error: error.message })
            inFlight.current.delete(flightKey)
        }
    }, [])

    // Fetch for any selected publication this issue and window have not loaded yet: on first load,
    // when publications arrive from the database, and when the window or issue changes.
    useEffect(() => {
        if (!currentIssueId || !query) return
        const windowCache = cache[bucket] || {}
        selectedPublications.forEach(pub => {
            if (!UUID_RE.test(pub.id)) {
                logger.warn(`⚠️ Skipping preview fetch for publication with invalid UUID: ${pub.id}`)
                return
            }
            if (!windowCache[pub.id]) fetchFor(pub.id)
        })
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedPublications, currentIssueId, bucket])

    const previewFor = (pubId) => {
        if (!query) return EMPTY
        const cached = cache[bucket]?.[pubId]
        if (cached) return cached
        // Only a request that can actually be made is "loading"; the rest would spin forever.
        return currentIssueId && UUID_RE.test(pubId) ? LOADING : WAITING
    }

    // Ask again for one publication, e.g. after an error or an empty answer given before it was linked.
    const retry = useCallback((pubId) => fetchFor(pubId, { force: true }), [fetchFor])

    // Drop a removed publication from every cached window to avoid stale data.
    const forget = useCallback((pubId) => {
        setCache(prev => {
            const next = {}
            for (const [key, windowData] of Object.entries(prev)) {
                const { [pubId]: _removed, ...rest } = windowData
                next[key] = rest
            }
            return next
        })
    }, [])

    return { previewFor, fetchFor, retry, forget }
}
