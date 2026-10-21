// Delivery-schedule helpers shared by the schedule pickers and the enable-automatic-delivery flow.
// Weekdays count from Monday = 0, matching the backend's schedule_weekday.

export const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

const SHORT_WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

export function browserTimezone() {
    try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
    } catch {
        return 'UTC'
    }
}

export function isValidTimezone(name) {
    if (!name) return false
    try {
        new Intl.DateTimeFormat('en', { timeZone: name })
        return true
    } catch {
        return false
    }
}

/** IANA timezones for the picker, always including `current` (and UTC) even if the runtime omits them. */
export function timezoneOptions(current) {
    let zones = []
    try {
        zones = Intl.supportedValuesOf('timeZone')
    } catch {
        // older runtimes: fall back to the zones we know the user has
    }
    return [...new Set(['UTC', ...zones, current, browserTimezone()].filter(isValidTimezone))].sort()
}

/** The weekday (Monday = 0) and day of month of `now` as seen in `timezone`. */
export function localDay(now = new Date(), timezone = 'UTC') {
    const zone = isValidTimezone(timezone) ? timezone : 'UTC'
    const parts = new Intl.DateTimeFormat('en-US', { timeZone: zone, weekday: 'short', day: 'numeric' }).formatToParts(now)
    const weekday = SHORT_WEEKDAYS.indexOf(parts.find((p) => p.type === 'weekday')?.value)
    return { weekday, dayOfMonth: Number(parts.find((p) => p.type === 'day')?.value) }
}

/**
 * Schedule columns to pin when automatic delivery is switched on, so the stored schedule says what
 * will happen: a weekly issue keeps today's weekday, a monthly one today's date. Values the owner
 * already chose are kept.
 */
export function anchorDefaults({ frequency, timezone, weekday, dayOfMonth }, now = new Date()) {
    const today = localDay(now, timezone)
    const fields = {}
    if (frequency === 'weekly' && (weekday === null || weekday === undefined)) fields.schedule_weekday = today.weekday
    if (frequency === 'monthly' && (dayOfMonth === null || dayOfMonth === undefined)) fields.schedule_day_of_month = today.dayOfMonth
    return fields
}

const ordinal = (n) => {
    const mod100 = n % 100
    if (mod100 >= 11 && mod100 <= 13) return `${n}th`
    return `${n}${{ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] || 'th'}`
}

/** "Every Monday at 09:00 (Europe/Berlin)" for the issue row's schedule columns. */
export function describeCadence(issue) {
    if (!issue) return ''
    const time = (issue.schedule_time_local || '09:00').slice(0, 5)
    const zone = issue.schedule_timezone || 'UTC'
    let when
    switch (issue.frequency) {
        case 'daily':
            when = 'Every day'
            break
        case 'weekly':
            when = issue.schedule_weekday == null ? 'Every week' : `Every ${WEEKDAYS[issue.schedule_weekday]}`
            break
        case 'monthly':
            when = issue.schedule_day_of_month == null ? 'Every month' : `On the ${ordinal(issue.schedule_day_of_month)} of every month`
            break
        default:
            return ''
    }
    return `${when} at ${time} (${zone})`
}

/** Whether the address saved on the issue is the one typed in the form and has been confirmed. */
export function isRecipientConfirmed(issue, typedEmail) {
    if (!issue?.target_email_verified_at) return false
    return (issue.target_email || '').trim().toLowerCase() === (typedEmail || '').trim().toLowerCase()
}

/**
 * Schedule columns to write together with auto_send = true: the browser's timezone while the issue
 * still has the database default (UTC), and the weekday / day of month it starts on. `current` is
 * the issue's stored schedule columns, or null for an issue that does not exist yet.
 */
export function scheduleOnEnable(frequency, current, now = new Date()) {
    const stored = current?.schedule_timezone
    const timezone = !stored || stored === 'UTC' ? browserTimezone() : stored
    const fields = timezone !== stored ? { schedule_timezone: timezone } : {}
    return {
        ...fields,
        ...anchorDefaults({
            frequency,
            timezone,
            weekday: current?.schedule_weekday,
            dayOfMonth: current?.schedule_day_of_month,
        }, now),
    }
}

/** What to tell the owner when the database refused to turn automatic delivery on. */
export function autoSendErrorMessage(error) {
    const text = `${error?.message || ''} ${error?.code || ''}`
    if (text.includes('recipient_not_verified') || text.includes('23514')) {
        return 'Confirm this address before turning on automatic delivery.'
    }
    return "Couldn't change automatic delivery. Try again."
}
