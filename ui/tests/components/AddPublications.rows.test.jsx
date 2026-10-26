import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

const mocks = vi.hoisted(() => ({ selected: [], toggleRemoveImages: vi.fn() }))

vi.mock('@/contexts/useSelectedPublications', () => ({
    useSelectedPublications: () => ({
        selectedPublications: mocks.selected,
        removePublication: vi.fn(),
        toggleRemoveImages: mocks.toggleRemoveImages,
    }),
}))
vi.mock('@/app/components/AddUrlModal', () => ({ default: () => null }))

import AddPublications from '@/app/components/AddPublications'

const article = (id) => ({ id, title: `Story ${id}`, content_url: `https://x/${id}`, author: 'A', date_published: '2026-10-20' })
const previews = (byId) => ({
    previewFor: (id) => byId[id] || { status: 'loaded', articles: [], error: '' },
    fetchFor: vi.fn(),
    forget: vi.fn(),
    retry: vi.fn(),
})

const renderRows = (byId) => render(
    <AddPublications onOpenSearch={() => {}} previews={previews(byId)} windowLabel="in the last week" />
)

beforeEach(() => {
    mocks.toggleRemoveImages.mockReset()
    mocks.selected = [
        { id: 'p1', name: 'Economics Explained', publisher: 'Economics Explained', url: 'https://a' },
        { id: 'p2', name: 'Kyla\'s Newsletter', publisher: 'Kyla Scanlon', url: 'https://b' },
    ]
})

describe('publication rows', () => {
    it('shows the author only when it differs from the title', () => {
        renderRows({})
        expect(screen.getByText('Kyla Scanlon')).toBeInTheDocument()
        expect(screen.getAllByText('Economics Explained')).toHaveLength(1)
    })

    it('says "No articles" inline for an empty window instead of filling a row', () => {
        renderRows({})
        expect(screen.getAllByText(/^No articles in the last week/)).toHaveLength(2)
    })

    it('tints only the row that is expanded', () => {
        const { container } = renderRows({ p2: { status: 'loaded', articles: [article('a1'), article('a2')], error: '' } })
        expect(container.querySelectorAll('.n2p-pub.is-open')).toHaveLength(0)

        const toggle = screen.getByRole('button', { name: /Show 2 articles from Kyla/ })
        expect(toggle).toHaveAttribute('aria-expanded', 'false')
        fireEvent.click(toggle)
        expect(screen.getByRole('button', { name: /Hide 2 articles from Kyla/ })).toHaveAttribute('aria-expanded', 'true')
        expect(container.querySelectorAll('.n2p-pub.is-open')).toHaveLength(1)
    })

    it('keeps the all-publications image switch beside the per-publication toggles', () => {
        const { unmount } = renderRows({})
        expect(screen.getAllByLabelText(/Remove images from/).length).toBeGreaterThan(0)
        unmount()
    })

    it('toggles only the publications that differ', () => {
        mocks.selected = [{ id: 'a', name: 'A', remove_images: true }, { id: 'b', name: 'B', remove_images: false }]
        renderRows({})
        fireEvent.click(screen.getByRole('checkbox', { name: 'Remove images from all publications' }))
        expect(mocks.toggleRemoveImages).toHaveBeenCalledTimes(1)
        expect(mocks.toggleRemoveImages).toHaveBeenCalledWith('b')
    })
})
