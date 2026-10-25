import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'

const UUID_A = '11111111-1111-4111-8111-111111111111'
const UUID_B = '22222222-2222-4222-8222-222222222222'

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn(), config: {}, selected: [] }))
vi.mock('@/lib/apiFetch', () => ({ apiFetch: mocks.apiFetch }))
vi.mock('@/contexts/useNewsletterConfig', () => ({ useNewsletterConfig: () => mocks.config }))
vi.mock('@/contexts/useSelectedPublications', () => ({ useSelectedPublications: () => ({ selectedPublications: mocks.selected }) }))

import { useArticlePreviews } from '@/lib/useArticlePreviews'

const reply = (articles, id = UUID_A) => ({
    ok: true,
    json: async () => ({ success: true, data: { articles_by_publication: { [id]: articles } } }),
})

beforeEach(() => {
    mocks.apiFetch.mockReset()
    mocks.config = { articleWindow: 'custom', frequency: 'weekly', dateFrom: '2026-01-01', dateTo: '2026-01-05', currentIssueId: 'issue-1' }
    mocks.selected = [{ id: UUID_A }]
})

describe('useArticlePreviews', () => {
    it('does not spin forever for a publication that cannot be asked about yet', () => {
        mocks.config = { ...mocks.config, currentIssueId: null }
        mocks.selected = [{ id: 'temp-handle' }]
        const { result } = renderHook(() => useArticlePreviews())
        expect(result.current.previewFor('temp-handle').status).toBe('waiting')
        expect(mocks.apiFetch).not.toHaveBeenCalled()
    })

    it('keeps one paper\'s answers away from the next', async () => {
        mocks.apiFetch.mockResolvedValue(reply([{ id: 'a1', title: 'One' }]))
        const { result, rerender } = renderHook(() => useArticlePreviews())
        await waitFor(() => expect(result.current.previewFor(UUID_A).status).toBe('loaded'))

        mocks.config = { ...mocks.config, currentIssueId: 'issue-2' }
        rerender()
        expect(result.current.previewFor(UUID_A).status).toBe('loading')
        await waitFor(() => expect(mocks.apiFetch).toHaveBeenCalledTimes(2))
    })

    it('can ask again after an error', async () => {
        mocks.apiFetch.mockResolvedValueOnce({ ok: false, status: 500, statusText: 'x', text: async () => '' })
        const { result } = renderHook(() => useArticlePreviews())
        await waitFor(() => expect(result.current.previewFor(UUID_A).status).toBe('error'))

        mocks.apiFetch.mockResolvedValueOnce(reply([{ id: 'a1', title: 'One' }]))
        await act(() => result.current.retry(UUID_A))
        expect(result.current.previewFor(UUID_A).articles).toHaveLength(1)
    })

    it('lets a forced fetch replace a request that is still in the air', async () => {
        let resolveFirst
        mocks.apiFetch.mockImplementationOnce(() => new Promise((r) => { resolveFirst = r }))
        const { result } = renderHook(() => useArticlePreviews())
        await waitFor(() => expect(mocks.apiFetch).toHaveBeenCalledTimes(1))

        mocks.apiFetch.mockResolvedValueOnce(reply([{ id: 'a1', title: 'Linked' }]))
        await act(() => result.current.fetchFor(UUID_A, { force: true }))
        expect(result.current.previewFor(UUID_A).articles).toHaveLength(1)

        // The early answer (0 articles, before the link existed) arrives late and is dropped.
        await act(async () => { resolveFirst(reply([])) })
        expect(result.current.previewFor(UUID_A).articles).toHaveLength(1)
    })

    it('fetches from the latest issue even when called through an old render', async () => {
        mocks.config = { ...mocks.config, currentIssueId: null }
        mocks.apiFetch.mockResolvedValue(reply([{ id: 'a1', title: 'One' }], UUID_B))
        mocks.selected = [{ id: UUID_B }]
        const { result, rerender } = renderHook(() => useArticlePreviews())
        const oldFetchFor = result.current.fetchFor // what a modal holds across its awaits

        mocks.config = { ...mocks.config, currentIssueId: 'issue-9' }
        rerender()
        await act(() => oldFetchFor(UUID_B, { force: true }))
        expect(mocks.apiFetch.mock.calls[0][0]).toContain('/api/articles/preview/issue-9')
    })
})
