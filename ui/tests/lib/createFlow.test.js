import { describe, it, expect } from 'vitest'
import {
    STEPS,
    stepFromHash,
    hashForStep,
    clampStep,
    articleWindowError,
    articleWindowQuery,
    articleWindowKey,
    toQueryString,
    describeArticleWindow,
    sheetsFilled,
    isStepDone,
} from '@/lib/createFlow'

describe('step hash', () => {
    it('maps each step to its hash and back', () => {
        STEPS.forEach((step, i) => {
            expect(hashForStep(i)).toBe(`#${step.key}`)
            expect(stepFromHash(`#${step.key}`)).toBe(i)
        })
    })

    it('starts at Add for an empty or unknown hash', () => {
        expect(stepFromHash('')).toBe(0)
        expect(stepFromHash(undefined)).toBe(0)
        expect(stepFromHash('#nope')).toBe(0)
    })

    it('keeps the step inside the flow', () => {
        expect(clampStep(-1)).toBe(0)
        expect(clampStep(9)).toBe(STEPS.length - 1)
        expect(clampStep(NaN)).toBe(0)
        expect(hashForStep(9)).toBe('#print')
    })
})

describe('article window', () => {
    it('turns a preset into days_back', () => {
        expect(articleWindowQuery({ articleWindow: '1' })).toEqual({ days_back: 1 })
        expect(articleWindowQuery({ articleWindow: '7' })).toEqual({ days_back: 7 })
        expect(articleWindowQuery({ articleWindow: '30' })).toEqual({ days_back: 30 })
    })

    it('falls back to the frequency, then to a week', () => {
        expect(articleWindowQuery({ articleWindow: undefined, frequency: 'monthly' })).toEqual({ days_back: 30 })
        expect(articleWindowQuery({})).toEqual({ days_back: 7 })
    })

    it('uses both dates for a custom range', () => {
        const config = { articleWindow: 'custom', dateFrom: '2026-10-01', dateTo: '2026-10-08' }
        expect(articleWindowQuery(config)).toEqual({ start_date: '2026-10-01', end_date: '2026-10-08' })
        expect(articleWindowError(config)).toBeNull()
    })

    it('says what is wrong with an incomplete or reversed custom range', () => {
        expect(articleWindowError({ articleWindow: 'custom', dateFrom: '', dateTo: '' })).toMatch(/Both dates are required/)
        expect(articleWindowError({ articleWindow: 'custom', dateFrom: '2026-10-09', dateTo: '2026-10-01' })).toMatch(/start date is after the end date/)
        expect(articleWindowQuery({ articleWindow: 'custom', dateFrom: '2026-10-09', dateTo: '2026-10-01' })).toBeNull()
        expect(articleWindowQuery({ articleWindow: 'custom', dateFrom: '2026-10-09' })).toBeNull()
    })

    it('never blocks a preset window', () => {
        expect(articleWindowError({ articleWindow: '7', dateFrom: '2026-10-09', dateTo: '2026-10-01' })).toBeNull()
    })

    it('keys the preview cache by window', () => {
        expect(articleWindowKey({ articleWindow: '7' })).toBe('days:7')
        expect(articleWindowKey({ articleWindow: 'custom', dateFrom: '2026-10-01', dateTo: '2026-10-08' })).toBe('custom:2026-10-01:2026-10-08')
        expect(articleWindowKey({ articleWindow: 'custom' })).toBe('custom:incomplete')
    })

    it('builds a query string', () => {
        expect(toQueryString({ days_back: 7 })).toBe('days_back=7')
        expect(toQueryString({ start_date: '2026-10-01', end_date: '2026-10-08' })).toBe('start_date=2026-10-01&end_date=2026-10-08')
    })

    it('describes the window for the masthead', () => {
        expect(describeArticleWindow({ articleWindow: '1' })).toBe('the last day')
        expect(describeArticleWindow({ articleWindow: '7' })).toBe('the last week')
        expect(describeArticleWindow({ articleWindow: '30' })).toBe('the last month')
        expect(describeArticleWindow({ articleWindow: 'custom', dateFrom: '2026-10-01', dateTo: '2026-10-08' })).toBe('2026-10-01 to 2026-10-08')
        expect(describeArticleWindow({ articleWindow: 'custom' })).toBe('custom dates')
    })
})

describe('stepper progress', () => {
    const base = { publicationCount: 0, title: '', format: 'essay', articleWindow: '7', dateFrom: '', dateTo: '', isGenerating: false, hasPdf: false }

    it('fills one Add sheet per publication, up to three', () => {
        expect(sheetsFilled(0, base)).toBe(0)
        expect(sheetsFilled(0, { ...base, publicationCount: 2 })).toBe(2)
        expect(sheetsFilled(0, { ...base, publicationCount: 8 })).toBe(3)
    })

    it('fills Configure sheets for format, title and a usable window', () => {
        expect(sheetsFilled(1, base)).toBe(2)
        expect(sheetsFilled(1, { ...base, title: 'Morning News' })).toBe(3)
        expect(sheetsFilled(1, { ...base, title: '  ', articleWindow: 'custom' })).toBe(1)
    })

    it('keeps Configure sunk until the reader has seen its controls (title still counts if set)', () => {
        expect(sheetsFilled(1, { ...base, visitedConfigure: false })).toBe(0)
        expect(sheetsFilled(1, { ...base, visitedConfigure: false, title: 'Morning News' })).toBe(1)
        expect(sheetsFilled(1, { ...base, visitedConfigure: true, title: 'Morning News' })).toBe(3)
    })

    it('fills Print sheets while the press runs and when a PDF exists', () => {
        expect(sheetsFilled(2, base)).toBe(0)
        expect(sheetsFilled(2, { ...base, isGenerating: true })).toBe(2)
        expect(sheetsFilled(2, { ...base, hasPdf: true })).toBe(3)
    })

    it('marks a step done only after the reader has moved past it with its work in place', () => {
        const withPubs = { ...base, publicationCount: 1 }
        expect(isStepDone(0, 1, 1, withPubs)).toBe(true)
        expect(isStepDone(0, 1, 1, base)).toBe(false)
        expect(isStepDone(0, 0, 1, withPubs)).toBe(false) // the current step is never "done"
        expect(isStepDone(1, 0, 0, withPubs)).toBe(false) // not reached yet
        expect(isStepDone(1, 2, 2, { ...withPubs, articleWindow: 'custom' })).toBe(false)
    })

    it('marks Print done once a PDF exists and the reader is elsewhere', () => {
        expect(isStepDone(2, 1, 2, { ...base, hasPdf: true })).toBe(true)
        expect(isStepDone(2, 1, 2, base)).toBe(false)
    })
})
