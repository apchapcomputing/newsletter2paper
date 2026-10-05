import { describe, it, expect } from 'vitest'
import { describeSchedule, friendlyError } from '@/utils/scheduleStatus'

describe('friendlyError', () => {
    it.each([
        ['pdf: renderer timed out', "We couldn't build the PDF from your newsletters (renderer timed out)"],
        ['email: Resend is unavailable (503: down)', "The email couldn't be sent (Resend is unavailable (503: down))"],
        ['config: no recipient email address is set', "Delivery isn't set up correctly (no recipient email address is set)"],
        ['email: Resend rate limit (gave up after 5 attempts)', "The email couldn't be sent (Resend rate limit (gave up after 5 attempts))"],
    ])('translates %s', (raw, expected) => {
        expect(friendlyError(raw)).toBe(expected)
    })

    it('passes unknown messages through unchanged', () => {
        expect(friendlyError('unexpected error: boom')).toBe('unexpected error: boom')
    })

    it.each([null, undefined, '', '   '])('returns null for %p', (value) => {
        expect(friendlyError(value)).toBeNull()
    })

    it('keeps the bare reason when a prefix has no detail', () => {
        expect(friendlyError('email:')).toBe("The email couldn't be sent")
    })
})

describe('describeSchedule', () => {
    it('shows the next delivery for a healthy issue', () => {
        const result = describeSchedule({ schedule_status: 'idle', next_run_at: '2026-10-09T13:00:00Z', last_run_error: null })
        expect(result.nextAt).toEqual(new Date('2026-10-09T13:00:00Z'))
        expect(result.retryAt).toBeNull()
        expect(result.error).toBeNull()
    })

    it('treats next_run_at as the retry time while a failed delivery is being retried', () => {
        const result = describeSchedule({ schedule_status: 'failed', next_run_at: '2026-10-05T10:00:00Z', last_run_error: 'email: down' })
        expect(result.retryAt).toEqual(new Date('2026-10-05T10:00:00Z'))
        expect(result.nextAt).toBeNull()      // the retry time is not the next regular delivery
        expect(result.error).toBe("The email couldn't be sent (down)")
    })

    it('keeps showing the last error after giving up, alongside the next regular delivery', () => {
        const result = describeSchedule({
            schedule_status: 'idle', next_run_at: '2026-10-06T09:00:00Z',
            last_run_error: 'email: Resend is unavailable (gave up after 5 attempts)',
        })
        expect(result.nextAt).toEqual(new Date('2026-10-06T09:00:00Z'))
        expect(result.retryAt).toBeNull()
        expect(result.error).toContain('gave up after 5 attempts')
    })

    it('copes with a missing issue and unparseable dates', () => {
        expect(describeSchedule(null)).toEqual({ nextAt: null, retryAt: null, error: null })
        expect(describeSchedule({ schedule_status: 'idle', next_run_at: 'not a date' }).nextAt).toBeNull()
    })
})
