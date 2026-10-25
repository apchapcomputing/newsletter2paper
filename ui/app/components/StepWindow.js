'use client'

import { useEffect, useRef } from 'react'
import { STEPS, LAST_STEP } from '../../lib/createFlow'

/**
 * The window that holds one step: a cornflower title bar over a raised page, the title and deck,
 * a rule, the step's fields and Back / Next written as jump lines. Moving to another step moves
 * focus to the title so keyboard and screen-reader users land at the top of the new step.
 * `nextBlocked` marks Next aria-disabled (it stays focusable so the reason can be reached);
 * the caller decides what a click does and names the explaining element in `nextDescribedBy`.
 */
export default function StepWindow({ index, onBack, onNext, nextBlocked = false, nextDescribedBy, children }) {
    const step = STEPS[index]
    const titleRef = useRef(null)
    const shown = useRef(index)

    useEffect(() => {
        // Compare with the step last shown, not "is this the first effect": Strict Mode re-runs
        // effects on mount, which would otherwise focus the title (and ring it) on page load.
        if (shown.current !== index) titleRef.current?.focus({ preventScroll: true })
        shown.current = index
    }, [index])

    return (
        <section className="n2p-window" aria-labelledby="step-title">
            <div className="n2p-window__bar">
                <span className="n2p-window__dots" aria-hidden="true"><i /><i /></span>
            </div>
            <div className="n2p-window__body">
                <h2 className="n2p-window__title" id="step-title" ref={titleRef} tabIndex={-1}>{step.title}</h2>
                <p className="n2p-deck">{step.deck}</p>
                <hr className="n2p-rule" />
                {children}
                <div className="n2p-window__nav">
                    {index > 0 ? (
                        <button type="button" className="n2p-btn" onClick={onBack}>
                            <span className="n2p-btn__ar" aria-hidden="true">←</span> Back to {STEPS[index - 1].label}
                        </button>
                    ) : <span />}
                    {index < LAST_STEP && (
                        <button
                            type="button"
                            className="n2p-btn n2p-btn--fill"
                            onClick={onNext}
                            aria-disabled={nextBlocked ? 'true' : undefined}
                            aria-describedby={nextBlocked ? nextDescribedBy : undefined}
                        >
                            Continued in {STEPS[index + 1].label} <span className="n2p-btn__ar" aria-hidden="true">→</span>
                        </button>
                    )}
                </div>
            </div>
        </section>
    )
}
