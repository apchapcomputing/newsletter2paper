import { describe, it, expect, vi } from 'vitest'
import {
    WEEKDAYS, anchorDefaults, autoSendErrorMessage, describeCadence, isRecipientConfirmed, isValidTimezone,
    localDay, scheduleOnEnable, timezoneOptions,
} from '@/lib/schedule'

// Wednesday 2026-10-14 23:30 UTC: already Thursday the 15th in Tokyo, still Wednesday in New York.
const LATE = new Date('2026-10-14T23:30:00Z')

describe('localDay', () => {
    it('counts weekdays from Monday = 0 in the given timezone', () => {
        expect(localDay(LATE, 'UTC')).toEqual({ weekday: 2, dayOfMonth: 14 })
        expect(localDay(LATE, 'Asia/Tokyo')).toEqual({ weekday: 3, dayOfMonth: 15 })
        expect(localDay(LATE, 'America/New_York')).toEqual({ weekday: 2, dayOfMonth: 14 })
    })

    it('treats Sunday as 6', () => {
        expect(localDay(new Date('2026-10-18T12:00:00Z'), 'UTC').weekday).toBe(6)
    })

    it('falls back to UTC for an unknown timezone', () => {
        expect(localDay(LATE, 'Mars/Olympus')).toEqual(localDay(LATE, 'UTC'))
    })
})

describe('anchorDefaults', () => {
    it('pins a weekly issue to today’s weekday in its timezone', () => {
        expect(anchorDefaults({ frequency: 'weekly', timezone: 'Asia/Tokyo' }, LATE)).toEqual({ schedule_weekday: 3 })
    })

    it('pins a monthly issue to today’s date', () => {
        expect(anchorDefaults({ frequency: 'monthly', timezone: 'UTC' }, LATE)).toEqual({ schedule_day_of_month: 14 })
    })

    it('keeps what the owner already chose, including Monday (0)', () => {
        expect(anchorDefaults({ frequency: 'weekly', timezone: 'UTC', weekday: 0 }, LATE)).toEqual({})
        expect(anchorDefaults({ frequency: 'monthly', timezone: 'UTC', dayOfMonth: 31 }, LATE)).toEqual({})
    })

    it('pins nothing for daily', () => {
        expect(anchorDefaults({ frequency: 'daily', timezone: 'UTC' }, LATE)).toEqual({})
    })
})

describe('scheduleOnEnable', () => {
    it('replaces the database default UTC with the browser timezone', () => {
        vi.spyOn(Intl.DateTimeFormat.prototype, 'resolvedOptions').mockReturnValue({ timeZone: 'Asia/Tokyo' })
        expect(scheduleOnEnable('weekly', { schedule_timezone: 'UTC' }, LATE))
            .toEqual({ schedule_timezone: 'Asia/Tokyo', schedule_weekday: 3 })
        expect(scheduleOnEnable('daily', null, LATE)).toEqual({ schedule_timezone: 'Asia/Tokyo' })
    })

    it('keeps a timezone the owner picked', () => {
        vi.spyOn(Intl.DateTimeFormat.prototype, 'resolvedOptions').mockReturnValue({ timeZone: 'Asia/Tokyo' })
        expect(scheduleOnEnable('weekly', { schedule_timezone: 'Europe/Berlin', schedule_weekday: 4 }, LATE)).toEqual({})
    })
})

describe('describeCadence', () => {
    it.each([
        [{ frequency: 'daily', schedule_time_local: '07:30', schedule_timezone: 'Europe/Berlin' }, 'Every day at 07:30 (Europe/Berlin)'],
        [{ frequency: 'weekly', schedule_weekday: 0 }, 'Every Monday at 09:00 (UTC)'],
        [{ frequency: 'weekly' }, 'Every week at 09:00 (UTC)'],
        [{ frequency: 'monthly', schedule_day_of_month: 1 }, 'On the 1st of every month at 09:00 (UTC)'],
        [{ frequency: 'monthly', schedule_day_of_month: 22 }, 'On the 22nd of every month at 09:00 (UTC)'],
        [{ frequency: 'monthly', schedule_day_of_month: 13 }, 'On the 13th of every month at 09:00 (UTC)'],
        [{ frequency: 'custom' }, ''],
    ])('%j', (issue, text) => expect(describeCadence(issue)).toBe(text))

    it('has a name for every weekday index', () => {
        expect(WEEKDAYS).toHaveLength(7)
        expect(WEEKDAYS[0]).toBe('Monday')
    })
})

describe('timezones', () => {
    it('validates IANA names', () => {
        expect(isValidTimezone('Europe/Berlin')).toBe(true)
        expect(isValidTimezone('Mars/Olympus')).toBe(false)
        expect(isValidTimezone('')).toBe(false)
    })

    it('lists the current zone and UTC, sorted without duplicates', () => {
        const zones = timezoneOptions('Europe/Berlin')
        expect(zones).toContain('UTC')
        expect(zones).toContain('Europe/Berlin')
        expect(new Set(zones).size).toBe(zones.length)
        expect([...zones].sort()).toEqual(zones)
    })
})

describe('isRecipientConfirmed', () => {
    const confirmed = { target_email: 'Me@Example.com', target_email_verified_at: '2026-10-01T00:00:00Z' }

    it('needs a confirmation and the typed address to match the saved one', () => {
        expect(isRecipientConfirmed(confirmed, ' me@example.com ')).toBe(true)
        expect(isRecipientConfirmed(confirmed, 'other@example.com')).toBe(false)
        expect(isRecipientConfirmed({ ...confirmed, target_email_verified_at: null }, 'me@example.com')).toBe(false)
        expect(isRecipientConfirmed(null, 'me@example.com')).toBe(false)
    })
})

describe('autoSendErrorMessage', () => {
    it('explains the unconfirmed-address refusal', () => {
        expect(autoSendErrorMessage({ message: 'recipient_not_verified: confirm the recipient' })).toMatch(/Confirm this address/)
        expect(autoSendErrorMessage({ code: '23514', message: 'x' })).toMatch(/Confirm this address/)
    })

    it('is generic for anything else', () => {
        expect(autoSendErrorMessage({ message: 'network down' })).toMatch(/Try again/)
        expect(autoSendErrorMessage(null)).toMatch(/Try again/)
    })
})
