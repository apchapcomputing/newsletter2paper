// The create flow: Add publications, Configure the paper, Print it. Pure helpers shared by the
// page, the stepper and the Configure step so step rules live in one place.

export const STEPS = [
    { key: 'add', label: 'Add', name: 'Publications', title: 'Add Publications' },
    { key: 'configure', label: 'Configure', name: 'Your paper', title: 'Configure Your Newspaper' },
    { key: 'print', label: 'Print', name: 'The issue', title: 'Print Your Newspaper Issue' },
]

export const LAST_STEP = STEPS.length - 1

// The step lives in the URL hash (#add, #configure, #print) so the browser's back button and
// deep links work without separate routes; the data itself is restored from the config contexts.
export function stepFromHash(hash) {
    const key = String(hash || '').replace(/^#/, '')
    const index = STEPS.findIndex((step) => step.key === key)
    return index === -1 ? 0 : index
}

export function hashForStep(index) {
    return `#${STEPS[clampStep(index)].key}`
}

export function clampStep(index) {
    return Math.max(0, Math.min(LAST_STEP, Number.isInteger(index) ? index : 0))
}

const DAYS_BY_WINDOW = { '1': 1, '7': 7, '30': 30 }
const DAYS_BY_FREQUENCY = { daily: 1, weekly: 7, monthly: 30 }

// Issues saved before the article window existed carry `frequency: 'custom'` with their dates and
// no usable window; they still mean a custom range, not the 7-day default.
const isCustomWindow = ({ articleWindow, frequency }) =>
    articleWindow === 'custom' || (!DAYS_BY_WINDOW[articleWindow] && frequency === 'custom')

/** Why the article window can't be used yet, or null. Only a custom range can be wrong. */
export function articleWindowError({ articleWindow, dateFrom, dateTo, frequency }) {
    if (!isCustomWindow({ articleWindow, frequency })) return null
    if (!dateFrom || !dateTo) return 'Both dates are required for a custom range. Pick a start and an end day.'
    if (dateFrom > dateTo) return 'The start date is after the end date. Pick an earlier day.'
    return null
}

/**
 * The window of articles to fetch, as the query the preview and PDF routes take:
 * `days_back` for a preset, `start_date` and `end_date` for a custom range.
 * Returns null while a custom range is incomplete or reversed.
 */
export function articleWindowQuery({ articleWindow, dateFrom, dateTo, frequency }) {
    if (isCustomWindow({ articleWindow, frequency })) {
        if (articleWindowError({ articleWindow, dateFrom, dateTo, frequency })) return null
        return { start_date: dateFrom, end_date: dateTo }
    }
    return { days_back: DAYS_BY_WINDOW[articleWindow] || DAYS_BY_FREQUENCY[frequency] || 7 }
}

/** A stable cache key for the current window. */
export function articleWindowKey(config) {
    const query = articleWindowQuery(config)
    if (!query) return 'custom:incomplete'
    return query.days_back ? `days:${query.days_back}` : `custom:${query.start_date}:${query.end_date}`
}

export function toQueryString(query) {
    return Object.entries(query).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&')
}

/** "the last week", for the masthead's right ear. */
export function describeArticleWindow({ articleWindow, dateFrom, dateTo, frequency }) {
    if (isCustomWindow({ articleWindow, frequency })) {
        return dateFrom && dateTo ? `${dateFrom} to ${dateTo}` : 'custom dates'
    }
    const days = articleWindowQuery({ articleWindow, frequency }).days_back
    if (days === 1) return 'the last day'
    if (days === 7) return 'the last week'
    if (days === 30) return 'the last month'
    return `the last ${days} days`
}

export function isStepComplete(index, { publicationCount, articleWindow, dateFrom, dateTo, frequency }) {
    if (index === 0) return publicationCount > 0
    if (index === 1) return !articleWindowError({ articleWindow, dateFrom, dateTo, frequency })
    return false
}

/** How many of a step's three sheets are filled (0 to 3). `visitedConfigure`: the reader has reached Configure. */
export function sheetsFilled(index, { publicationCount, title, articleWindow, dateFrom, dateTo, frequency, format, isGenerating, hasPdf, visitedConfigure = true }) {
    if (index === 0) return Math.min(3, publicationCount)
    if (index === 1) {
        // Format and window always hold a default; they only count once the reader has seen them.
        return [visitedConfigure && Boolean(format), Boolean((title || '').trim()), visitedConfigure && !articleWindowError({ articleWindow, dateFrom, dateTo, frequency })]
            .filter(Boolean).length
    }
    if (hasPdf) return 3
    return isGenerating ? 2 : 0
}

/** A step tile is "done" once the reader has moved past it and what it asks for is in place. */
export function isStepDone(index, current, reached, state) {
    if (index === current) return false
    if (index === LAST_STEP) return Boolean(state.hasPdf)
    return index < reached && isStepComplete(index, state)
}
