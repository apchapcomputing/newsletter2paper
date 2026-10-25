import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('@/lib/analytics', () => ({
    track: vi.fn(),
    consent: { status: () => null, accept: vi.fn(), decline: vi.fn() },
}))
vi.mock('@/contexts/useAuth', () => ({
    useAuth: () => ({ signInWithMagicLink: vi.fn(), signInWithProvider: vi.fn() }),
}))
// Plain anchors: the real Link would try to route, which jsdom can't do.
vi.mock('next/link', () => ({
    default: ({ href, children, ...props }) => <a href={href} {...props}>{children}</a>,
}))

import { track } from '@/lib/analytics'
import Landing from '@/app/welcome/Landing'

const SAMPLES = [
    { id: 'newspaper', label: 'Newspaper layout', href: '/samples/sample-newspaper.pdf' },
    { id: 'essay', label: 'Essay layout', href: '/samples/sample-essay.pdf' },
]

// Links point at real routes; stop jsdom from trying to navigate when they are clicked.
const stopNavigation = (e) => e.preventDefault()

describe('Landing analytics', () => {
    beforeEach(() => {
        track.mockClear()
        document.addEventListener('click', stopNavigation)
    })
    afterEach(() => document.removeEventListener('click', stopNavigation))

    it('sends nothing on render', () => {
        render(<Landing samples={SAMPLES} photos={[]} heroImage={null} />)
        expect(track).not.toHaveBeenCalled()
    })

    it('records landing_cta_clicked with the location for each CTA that goes to the app', async () => {
        const user = userEvent.setup()
        render(<Landing samples={[]} photos={[]} heroImage={null} />)

        const makeFirst = screen.getAllByRole('link', { name: 'Make my first PDF' })
        expect(makeFirst).toHaveLength(2) // hero, then the closing CTA

        await user.click(makeFirst[0])
        expect(track).toHaveBeenLastCalledWith('landing_cta_clicked', { location: 'hero', target: 'app' })

        await user.click(screen.getByRole('link', { name: 'Make a PDF' }))
        expect(track).toHaveBeenLastCalledWith('landing_cta_clicked', { location: 'pricing_free', target: 'app' })

        await user.click(makeFirst[1])
        expect(track).toHaveBeenLastCalledWith('landing_cta_clicked', { location: 'footer', target: 'app' })
        expect(track).toHaveBeenCalledTimes(3)
    })

    it('opens the auth modal with trigger "landing" from the paid plan, after recording the click', async () => {
        const user = userEvent.setup()
        render(<Landing samples={[]} photos={[]} heroImage={null} />)
        expect(track).not.toHaveBeenCalledWith('auth_modal_opened', expect.anything())

        await user.click(screen.getByRole('button', { name: 'Create an account' }))

        expect(track.mock.calls).toEqual([
            ['landing_cta_clicked', { location: 'pricing_paid', target: 'signup' }],
            ['auth_modal_opened', { trigger: 'landing' }],
        ])
    })

    it('records sample_pdf_viewed with the sample id', async () => {
        const user = userEvent.setup()
        render(<Landing samples={SAMPLES} photos={[]} heroImage={null} />)

        const newspaper = screen.getByRole('link', { name: /View a sample: Newspaper layout/ })
        expect(newspaper).toHaveAttribute('href', '/samples/sample-newspaper.pdf')
        await user.click(newspaper)
        expect(track).toHaveBeenLastCalledWith('sample_pdf_viewed', { sample: 'newspaper' })

        await user.click(screen.getByRole('link', { name: /View a sample: Essay layout/ }))
        expect(track).toHaveBeenLastCalledWith('sample_pdf_viewed', { sample: 'essay' })
    })

    it('shows no sample links when there are no sample files', () => {
        render(<Landing samples={[]} photos={[]} heroImage={null} />)
        expect(screen.queryByRole('link', { name: /View a sample/ })).not.toBeInTheDocument()
    })
})
