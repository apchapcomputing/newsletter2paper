/**
 * Turns the scheduler's server-side fields on an issue (schedule_status, next_run_at,
 * last_run_error) into what the owner should see.
 *
 * The scheduler prefixes stored errors with where they came from: `pdf:` (building the PDF),
 * `email:` (the provider refused or failed) or `config:` (our setup is wrong).
 */

const ERROR_PREFIXES = {
    pdf: "We couldn't build the PDF from your newsletters",
    email: "The email couldn't be sent",
    config: "Delivery isn't set up correctly",
}

export function friendlyError(error) {
    const text = (error || '').trim()
    if (!text) return null
    const index = text.indexOf(':')
    const prefix = index > 0 ? text.slice(0, index) : ''
    if (!ERROR_PREFIXES[prefix]) return text
    const detail = text.slice(index + 1).trim()
    return detail ? `${ERROR_PREFIXES[prefix]} (${detail})` : ERROR_PREFIXES[prefix]
}

const toDate = (value) => {
    if (!value) return null
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? null : date
}

/**
 * @param {{schedule_status?: string, next_run_at?: string|null, last_run_error?: string|null}|null} issue
 * @returns {{nextAt: Date|null, retryAt: Date|null, error: string|null}}
 *   retryAt: when the scheduler will try again (only while it is retrying).
 *   nextAt:  the next regular delivery (not set while retrying, since next_run_at is the retry time).
 *   error:   the most recent failure, in plain language; cleared by the server on the next success.
 */
export function describeSchedule(issue) {
    if (!issue) return { nextAt: null, retryAt: null, error: null }
    const at = toDate(issue.next_run_at)
    const retrying = issue.schedule_status === 'failed'
    return {
        nextAt: retrying ? null : at,
        retryAt: retrying ? at : null,
        error: friendlyError(issue.last_run_error),
    }
}
