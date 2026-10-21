import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'

const auth = vi.hoisted(() => ({ value: { user: null, session: null } }))
vi.mock('@/contexts/useAuth', () => ({ useAuth: () => auth.value }))

import { SelectedPublicationsProvider, useSelectedPublications } from '@/contexts/useSelectedPublications'

const STORAGE_KEY = 'selectedPublications'
const wrapper = ({ children }) => <SelectedPublicationsProvider>{children}</SelectedPublicationsProvider>
const pub = (id, extra = {}) => ({ id, title: `Pub ${id}`, ...extra })

async function setup() {
    const hook = renderHook(() => useSelectedPublications(), { wrapper })
    await waitFor(() => expect(hook.result.current.isLoaded).toBe(true))
    return hook
}

const stored = () => JSON.parse(localStorage.getItem(STORAGE_KEY))

beforeEach(() => {
    localStorage.clear()
    auth.value = { user: null, session: null }
})

describe('useSelectedPublications', () => {
    it('refuses to be used outside its provider', () => {
        vi.spyOn(console, 'error').mockImplementation(() => {})
        expect(() => renderHook(() => useSelectedPublications())).toThrow(/within a SelectedPublicationsProvider/)
    })

    describe('selection', () => {
        it('adds a publication with remove_images defaulting to false', async () => {
            const { result } = await setup()
            act(() => result.current.addPublication(pub('a')))
            expect(result.current.selectedPublications).toEqual([{ id: 'a', title: 'Pub a', remove_images: false }])
        })

        it('keeps an explicit remove_images=true when adding', async () => {
            const { result } = await setup()
            act(() => result.current.addPublication(pub('a', { remove_images: true })))
            expect(result.current.selectedPublications[0].remove_images).toBe(true)
        })

        it('ignores duplicates, so the same newsletter is never printed twice', async () => {
            const { result } = await setup()
            act(() => {
                result.current.addPublication(pub('a'))
                result.current.addPublication(pub('a', { title: 'again' }))
            })
            expect(result.current.selectedPublications).toHaveLength(1)
            expect(result.current.selectedPublications[0].title).toBe('Pub a')
        })

        it('removes only the requested publication', async () => {
            const { result } = await setup()
            act(() => { result.current.addPublication(pub('a')); result.current.addPublication(pub('b')) })
            act(() => result.current.removePublication('a'))
            expect(result.current.selectedPublications.map(p => p.id)).toEqual(['b'])
        })

        it('toggles remove_images for one publication only', async () => {
            const { result } = await setup()
            act(() => { result.current.addPublication(pub('a')); result.current.addPublication(pub('b')) })
            act(() => result.current.toggleRemoveImages('a'))
            expect(result.current.selectedPublications.map(p => p.remove_images)).toEqual([true, false])
            act(() => result.current.toggleRemoveImages('a'))
            expect(result.current.selectedPublications.map(p => p.remove_images)).toEqual([false, false])
        })

        it('swaps a temporary id for the saved database id, keeping the other fields', async () => {
            const { result } = await setup()
            act(() => result.current.addPublication(pub('tmp-1', { remove_images: true })))
            act(() => result.current.updatePublicationId('tmp-1', 'db-uuid'))
            expect(result.current.selectedPublications).toEqual([{ id: 'db-uuid', title: 'Pub tmp-1', remove_images: true }])
        })

        it('clears everything', async () => {
            const { result } = await setup()
            act(() => { result.current.addPublication(pub('a')); result.current.addPublication(pub('b')) })
            act(() => result.current.clearAllPublications())
            expect(result.current.selectedPublications).toEqual([])
        })
    })

    describe('persistence', () => {
        it('writes the selection to localStorage as it changes', async () => {
            const { result } = await setup()
            act(() => result.current.addPublication(pub('a')))
            await waitFor(() => expect(stored()).toEqual([{ id: 'a', title: 'Pub a', remove_images: false }]))
        })

        it('does not overwrite saved data with an empty list before it has loaded it', async () => {
            localStorage.setItem(STORAGE_KEY, JSON.stringify([pub('saved')]))
            auth.value = { user: { id: 'u1' }, session: { access_token: 't' } }

            const { result } = await setup()

            expect(result.current.selectedPublications.map(p => p.id)).toEqual(['saved'])
            expect(stored().map(p => p.id)).toEqual(['saved'])
        })

        it('survives corrupt saved JSON by starting empty', async () => {
            vi.spyOn(console, 'error').mockImplementation(() => {})
            localStorage.setItem(STORAGE_KEY, '{not json')
            const { result } = await setup()
            expect(result.current.selectedPublications).toEqual([])
        })
    })

    describe('guests vs. logging out', () => {
        // Guests have no database: localStorage is their only copy of the selection.
        it('keeps a guest’s saved selection after loading', async () => {
            localStorage.setItem(STORAGE_KEY, JSON.stringify([pub('guest-pick')]))
            auth.value = { user: null, session: null }

            const { result } = await setup()
            await act(async () => {}) // let follow-up effects run

            expect(result.current.selectedPublications.map(p => p.id)).toEqual(['guest-pick'])
        })

        it('clears the selection when a signed-in user logs out (so the next person on the device starts clean)', async () => {
            auth.value = { user: { id: 'u1' }, session: { access_token: 't' } }
            const hook = renderHook(() => useSelectedPublications(), { wrapper })
            await waitFor(() => expect(hook.result.current.isLoaded).toBe(true))
            act(() => hook.result.current.addPublication(pub('mine')))

            auth.value = { user: null, session: null }
            hook.rerender()

            await waitFor(() => expect(hook.result.current.selectedPublications).toEqual([]))
        })
    })
})
