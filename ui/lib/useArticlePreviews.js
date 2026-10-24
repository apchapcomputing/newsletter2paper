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

/**
 * Articles that would be printed for each selected publication, for the current article window.
 * Lives above the steps so the Add step's lists and the Print step's front page read one source.
 *
 * The cache is keyed by window → publication id → {status, articles, error}, so switching the
 * window back and forth serves from memory.
 */
export function useArticlePreviews() {
    const { selectedPublications } = useSelectedPublications()
    const { articleWindow, frequency, dateFrom, dateTo, currentIssueId } = useNewsletterConfig()
    const [cache, setCache] = useState({})
    const inFlight = useRef(new Set())

    const windowConfig = { articleWindow, frequency, dateFrom, dateTo }
    const windowKey = articleWindowKey(windowConfig)
    const query = articleWindowQuery(windowConfig)

    // Retries run after the render that scheduled them; read the live selection there.
    const selectedRef = useRef(selectedPublications)
    selectedRef.current = selectedPublications

    const fetchFor = useCallback(async (pubId, retryCount = 0) => {
        if (!currentIssueId || !pubId) {
            logger.log('⚠️ Missing issue ID or publication ID, skipping fetch')
            return
        }
        if (!query) return // A custom range that is not ready yet

        // Capture the window at call time so async writes land in the right bucket.
        const key = windowKey
        const flightKey = `${key}:${pubId}`
        if (retryCount === 0 && inFlight.current.has(flightKey)) return
        inFlight.current.add(flightKey)

        const setEntry = (entry) =>
            setCache(prev => ({ ...prev, [key]: { ...prev[key], [pubId]: entry } }))

        setEntry(LOADING)

        try {
            const response = await apiFetch(
                `/api/articles/preview/${currentIssueId}?${toQueryString(query)}&publication_id=${pubId}`
            )

            if (!response.ok) {
                const errorText = await response.text()
                logger.error(`Failed to fetch previews (${response.status}):`, errorText)
                throw new Error(`Failed to fetch article previews: ${response.status} ${response.statusText}`)
            }

            const result = await response.json()

            if (result.success && result.data) {
                const articles = result.data.articles_by_publication?.[pubId] || []
                const pubExists = selectedRef.current.some(p => p.id === pubId)

                // Retry for preset windows only: for a custom range, 0 articles is a valid answer.
                if (articles.length === 0 && pubExists && retryCount < MAX_RETRIES && articleWindow !== 'custom') {
                    logger.log(`🔄 Retry ${retryCount + 1}/${MAX_RETRIES} for publication ${pubId} after ${RETRY_DELAYS[retryCount]}ms`)
                    setTimeout(() => fetchFor(pubId, retryCount + 1), RETRY_DELAYS[retryCount])
                    return
                }

                setEntry({ status: 'loaded', articles, error: '' })
                logger.log(`✅ Loaded ${articles.length} articles for "${key}" / ${pubId}`)
            } else {
                setEntry(EMPTY)
            }
            inFlight.current.delete(flightKey)
        } catch (error) {
            logger.error(`Error fetching articles for publication ${pubId}:`, error)
            setEntry({ status: 'error', articles: [], error: error.message })
            inFlight.current.delete(flightKey)
        }
    }, [currentIssueId, query, windowKey, articleWindow])

    // Fetch for any selected publication this window has not loaded yet: on first load, when
    // publications arrive from the database, and when the window changes.
    useEffect(() => {
        if (!currentIssueId || !query) return
        const windowCache = cache[windowKey] || {}
        selectedPublications.forEach(pub => {
            if (!UUID_RE.test(pub.id)) {
                logger.warn(`⚠️ Skipping preview fetch for publication with invalid UUID: ${pub.id}`)
                return
            }
            if (!windowCache[pub.id]) fetchFor(pub.id)
        })
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedPublications, currentIssueId, windowKey])

    const previewFor = (pubId) => {
        if (!query) return EMPTY
        return cache[windowKey]?.[pubId] || LOADING
    }

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

    return { previewFor, fetchFor, forget }
}
