import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import Stepper from '@/app/components/Stepper'
import StepWindow from '@/app/components/StepWindow'
import OptionButtons from '@/app/components/OptionButtons'
import FrontPagePreview from '@/app/components/FrontPagePreview'
import PrintPress from '@/app/components/PrintPress'
import { frontPageStories } from '@/app/components/PrintStep'

vi.mock('@/contexts/useNewsletterConfig', () => ({ useNewsletterConfig: () => ({ currentIssueId: 'i1' }) }))
vi.mock('@/contexts/useSelectedPublications', () => ({ useSelectedPublications: () => ({ selectedPublications: [] }) }))
vi.mock('@/app/components/FakeDoor', () => ({ default: () => null }))

describe('Stepper', () => {
    it('names every step, marks the current one and jumps on click', () => {
        const onSelect = vi.fn()
        render(<Stepper current={1} sheets={[3, 1, 0]} done={[true, false, false]} onSelect={onSelect} />)

        const tiles = screen.getAllByRole('button')
        expect(tiles).toHaveLength(3)
        expect(tiles[0]).toHaveAccessibleName('Step 1, Add: Publications, done')
        expect(tiles[1]).toHaveAttribute('aria-current', 'step')
        expect(tiles[0]).not.toHaveAttribute('aria-current')

        fireEvent.click(tiles[2])
        expect(onSelect).toHaveBeenCalledWith(2)
    })

    it('fills sheets to match progress, and every sheet of a done step', () => {
        const { container } = render(<Stepper current={1} sheets={[0, 2, 0]} done={[true, false, false]} onSelect={() => {}} />)
        const stacks = container.querySelectorAll('.n2p-stack')
        expect(stacks[0].querySelectorAll('.is-filled')).toHaveLength(3)
        expect(stacks[1].querySelectorAll('.is-filled')).toHaveLength(2)
        expect(stacks[1].querySelectorAll('.is-typing')).toHaveLength(1)
        expect(stacks[2].querySelectorAll('.is-filled')).toHaveLength(0)
    })
})

describe('StepWindow', () => {
    const renderStep = (index, props = {}) => render(
        <StepWindow index={index} onBack={props.onBack || (() => {})} onNext={props.onNext || (() => {})} {...props}>
            <p>fields</p>
        </StepWindow>
    )

    it('shows the live summary in the bottom strip', () => {
        renderStep(1, { summary: '6 newsletters · 8 articles in the last week' })
        expect(screen.getByText('6 newsletters · 8 articles in the last week')).toBeInTheDocument()
    })

    it('hides Back on the first step and Next on the last', () => {
        const first = renderStep(0)
        expect(screen.queryByRole('button', { name: /Back to/ })).not.toBeInTheDocument()
        expect(screen.getByRole('button', { name: /Continued in Configure/ })).toBeInTheDocument()
        first.unmount()

        renderStep(2)
        expect(screen.getByRole('button', { name: /Back to Configure/ })).toBeInTheDocument()
        expect(screen.queryByRole('button', { name: /Continued in/ })).not.toBeInTheDocument()
    })

    it('writes Back and Next as jump lines and calls the handlers', () => {
        const onBack = vi.fn()
        const onNext = vi.fn()
        renderStep(1, { onBack, onNext })

        fireEvent.click(screen.getByRole('button', { name: /Back to Add/ }))
        fireEvent.click(screen.getByRole('button', { name: /Continued in Print/ }))
        expect(onBack).toHaveBeenCalledTimes(1)
        expect(onNext).toHaveBeenCalledTimes(1)
    })

    it('titles the window with the step and labels it for assistive tech', () => {
        renderStep(1)
        expect(screen.getByRole('region', { name: 'Configure Your Newspaper' })).toBeInTheDocument()
    })

    it('keeps Next focusable but aria-disabled when blocked, pointing at the reason', () => {
        renderStep(1, { nextBlocked: true, nextDescribedBy: 'date-error' })
        const next = screen.getByRole('button', { name: /Continued in Print/ })
        expect(next).toHaveAttribute('aria-disabled', 'true')
        expect(next).toHaveAttribute('aria-describedby', 'date-error')
        expect(next).toBeEnabled()
    })

    it('moves focus to the new step title when the step changes', () => {
        const { rerender } = renderStep(0)
        rerender(
            <StepWindow index={1} onBack={() => {}} onNext={() => {}}><p>fields</p></StepWindow>
        )
        expect(screen.getByRole('heading', { name: 'Configure Your Newspaper' })).toHaveFocus()
    })
})

describe('OptionButtons', () => {
    it('presses the selected option and reports changes', () => {
        const onChange = vi.fn()
        render(
            <>
                <span id="lbl">Format</span>
                <OptionButtons labelId="lbl" options={[{ value: 'a', label: 'Alpha' }, { value: 'b', label: 'Beta' }]} value="a" onChange={onChange} />
            </>
        )
        expect(screen.getByRole('group', { name: 'Format' })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Alpha' })).toHaveAttribute('aria-pressed', 'true')
        expect(screen.getByRole('button', { name: 'Beta' })).toHaveAttribute('aria-pressed', 'false')

        fireEvent.click(screen.getByRole('button', { name: 'Beta' }))
        expect(onChange).toHaveBeenCalledWith('b')
    })
})

describe('front page', () => {
    const article = (...titles) => ({ articles: titles.map((title, i) => ({ id: `a${i}`, title, subtitle: i === 0 ? 'A deck' : undefined })) })

    it('sets one story per article, newsletter by newsletter, and skips empty newsletters', () => {
        const previews = { p1: article('Lead story', 'Second'), p2: { articles: [] }, p3: article('Third') }
        const stories = frontPageStories(
            [{ id: 'p1', name: 'Field Notes' }, { id: 'p2', name: 'Quiet Letter' }, { id: 'p3', title: 'Tidepool' }],
            (id) => previews[id]
        )
        expect(stories).toEqual([
            { id: 'p1:a0', headline: 'Lead story', deck: 'A deck', publication: 'Field Notes' },
            { id: 'p1:a1', headline: 'Second', deck: undefined, publication: 'Field Notes' },
            { id: 'p3:a0', headline: 'Third', deck: 'A deck', publication: 'Tidepool' },
        ])
    })

    it('counts and lays out every article, not just two columns', () => {
        const stories = Array.from({ length: 7 }, (_, i) => ({ id: `s${i}`, headline: `Story ${i}`, publication: i < 4 ? 'A' : 'B' }))
        const { container } = render(<FrontPagePreview title="T" dateLabel="d" stories={stories} emptyMessage="" />)
        expect(container.textContent).toContain('7 stories')
        expect(container.querySelectorAll('.n2p-story')).toHaveLength(7)
    })

    it('renders the lead, bylines and a story count', () => {
        const { container } = render(
            <FrontPagePreview
                title="Morning News"
                dateLabel="Oct 24, 2026"
                stories={[
                    { headline: 'Lead story', deck: 'A deck', publication: 'Field Notes' },
                    { headline: 'Second story', publication: 'Tidepool' },
                ]}
                emptyMessage="nothing"
            />
        )
        expect(screen.getByRole('img', { name: 'Preview of the front page of Morning News' })).toBeInTheDocument()
        expect(container.textContent).toContain('Lead story')
        expect(container.textContent).toContain('By Field Notes')
        expect(container.textContent).toContain('2 stories')
        expect(container.querySelectorAll('.n2p-frontpage__reg')).toHaveLength(4)
    })

    it('shows the essay layout when essay is the chosen format', () => {
        const stories = [
            { id: 'a', headline: 'Opening piece', deck: 'Some words', publication: 'A' },
            { id: 'b', headline: 'Second piece', publication: 'B' },
        ]
        const { container } = render(<FrontPagePreview title="T" dateLabel="d" stories={stories} emptyMessage="" format="essay" />)
        expect(screen.getByRole('img', { name: 'Preview of the opening page of T' })).toBeInTheDocument()
        expect(container.querySelector('.n2p-essay')).not.toBeNull()
        expect(container.querySelector('.n2p-cols')).toBeNull()
        expect(container.textContent).toContain('2 pieces')
        expect(container.textContent).toContain('+ 1 more piece to follow')
    })

    it('says so when there is nothing to print', () => {
        const { container } = render(<FrontPagePreview title="T" dateLabel="d" stories={[]} emptyMessage="No stories yet." />)
        expect(container.textContent).toContain('No stories yet.')
        expect(container.textContent).toContain('0 stories')
    })
})

describe('PrintPress', () => {
    let onPrint
    let onStop
    beforeEach(() => {
        onPrint = vi.fn()
        onStop = vi.fn()
    })

    it('names the paper on the button and prints on click', () => {
        render(<PrintPress paperName="Morning News" isPrinting={false} status="" onPrint={onPrint} onStop={onStop} />)
        fireEvent.click(screen.getByRole('button', { name: 'Print Morning News' }))
        expect(onPrint).toHaveBeenCalledTimes(1)
    })

    it('shows the running press, locks the button and lets the reader stop it', () => {
        render(<PrintPress paperName="Morning News" isPrinting status="Setting type, inking the plates…" onPrint={onPrint} onStop={onStop} />)
        const button = screen.getByRole('button', { name: 'Printing Morning News…' })
        expect(button).toBeDisabled()
        expect(button).toHaveAttribute('aria-busy', 'true')
        expect(screen.getByText('Setting type, inking the plates…')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: 'Stop the presses' }))
        expect(onStop).toHaveBeenCalledTimes(1)
    })

    it('stays locked when there is nothing to print', () => {
        render(<PrintPress paperName="Morning News" isPrinting={false} disabled status="Add at least one newsletter before printing." onPrint={onPrint} onStop={onStop} />)
        expect(screen.getByRole('button', { name: 'Print Morning News' })).toBeDisabled()
    })
})
