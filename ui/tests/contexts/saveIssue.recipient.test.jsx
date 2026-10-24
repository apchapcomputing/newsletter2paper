import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'

const h = vi.hoisted(() => ({ auth: { user: null, session: null }, calls: [], results: {} }))
vi.mock('@/contexts/useAuth', () => ({ useAuth: () => h.auth }))
vi.mock('@/lib/analytics', () => ({ track: vi.fn() }))

// A Supabase query-builder stand-in: every chained call returns the builder; insert / update / upsert
// are recorded, and awaiting or .single() yields the canned result for "<table>.<op>".
vi.mock('@/lib/supabase', () => ({
    createClient: () => ({
        from: (table) => {
            const q = { table, op: 'select', payload: null }
            const builder = new Proxy({}, {
                get(_, prop) {
                    if (prop === 'then') return (resolve) => { h.calls.push({ ...q }); resolve(h.results[`${table}.${q.op}`] ?? { data: null, error: null }) }
                    return (...args) => {
                        if (['insert', 'update', 'upsert'].includes(prop)) { q.op = prop; q.payload = args[0] }
                        if (prop === 'single' || prop === 'maybeSingle') {
                            h.calls.push({ ...q })
                            return Promise.resolve(h.results[`${table}.${q.op}`] ?? { data: null, error: null })
                        }
                        return builder
                    }
                },
            })
            return builder
        },
        auth: { getSession: async () => ({ data: { session: null } }) },
    }),
}))

import { NewsletterConfigProvider, useNewsletterConfig } from '@/contexts/useNewsletterConfig'

const wrapper = ({ children }) => <NewsletterConfigProvider>{children}</NewsletterConfigProvider>
const ISSUE = { id: 'issue-1', target_email: 'me@example.com' }

async function setup() {
    const hook = renderHook(() => useNewsletterConfig(), { wrapper })
    await waitFor(() => expect(hook.result.current.isLoaded).toBe(true))
    return hook
}

const writes = (table, op) => h.calls.filter((c) => c.table === table && c.op === op)

beforeEach(() => {
    localStorage.clear()
    h.calls.length = 0
    h.results = {}
    h.auth = { user: { id: 'u1', email: 'me@example.com' }, session: { access_token: 't' } }
})

describe('saving an issue with a delivery address that is not the account email', () => {
    it('inserts with the account email, links the owner, then saves the typed address', async () => {
        h.results['issues.insert'] = { data: { ...ISSUE }, error: null }
        h.results['issues.update'] = { data: { ...ISSUE, target_email: 'friend@example.com' }, error: null }
        const { result } = await setup()
        act(() => result.current.updateTargetEmail('friend@example.com'))

        let saved
        await act(async () => { saved = await result.current.saveIssueToSupabase({ title: 'T', format: 'essay', frequency: 'weekly' }) })

        const [insert] = writes('issues', 'insert')
        expect(insert.payload.target_email).toBe('me@example.com')      // RLS: a new unlinked row is only visible via the creator's own address
        const order = h.calls.map((c) => `${c.table}.${c.op}`)
        expect(order.indexOf('user_issues.upsert')).toBeGreaterThan(order.indexOf('issues.insert'))
        expect(order.indexOf('issues.update')).toBeGreaterThan(order.indexOf('user_issues.upsert'))
        expect(writes('issues', 'update')[0].payload).toEqual({ target_email: 'friend@example.com' })
        expect(saved.target_email).toBe('friend@example.com')
    })

    it('does not make a second write when the typed address is the account email', async () => {
        h.results['issues.insert'] = { data: { ...ISSUE }, error: null }
        const { result } = await setup()
        act(() => result.current.updateTargetEmail('ME@example.com'))

        await act(async () => { await result.current.saveIssueToSupabase({ title: 'T' }) })

        expect(writes('issues', 'update')).toHaveLength(0)
    })

    it('updates an existing issue in place with the typed address', async () => {
        h.results['issues.update'] = { data: { ...ISSUE, target_email: 'friend@example.com' }, error: null }
        h.results['user_issues.select'] = { data: [{ user_id: 'u1' }], error: null }
        const { result } = await setup()
        act(() => { result.current.updateIssueId('issue-1'); result.current.updateTargetEmail('friend@example.com') })

        await act(async () => { await result.current.saveIssueToSupabase({ title: 'T' }) })

        expect(writes('issues', 'insert')).toHaveLength(0)
        expect(writes('issues', 'update')[0].payload.target_email).toBe('friend@example.com')
    })

    it('surfaces a failure to save the typed address instead of swallowing it', async () => {
        h.results['issues.insert'] = { data: { ...ISSUE }, error: null }
        h.results['issues.update'] = { data: null, error: { message: 'denied', code: '42501' } }
        const { result } = await setup()
        act(() => result.current.updateTargetEmail('friend@example.com'))

        await expect(act(async () => { await result.current.saveIssueToSupabase({ title: 'T' }) })).rejects.toMatchObject({ code: '42501' })
    })
})
