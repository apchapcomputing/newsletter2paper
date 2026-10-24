import { STEPS } from '../../lib/createFlow'

// Three sheets that fill with cornflower as a step's sub-tasks are finished. The one being
// worked on is drawn in raised paper with orange lines.
function PaperStack({ filled, typing }) {
    return (
        <svg className="n2p-stack" viewBox="0 0 34 34" aria-hidden="true">
            {[0, 1, 2].map((i) => {
                const x = 2 + i * 4
                const y = 10 - i * 4
                const state = i < filled ? 'is-filled' : (typing && i === filled ? 'is-typing' : '')
                return (
                    <g key={i} className={state}>
                        <rect className="pg" x={x} y={y} width="20" height="22" />
                        <rect className="ln" x={x + 4} y={y + 5} width="12" height="2" />
                        <rect className="ln" x={x + 4} y={y + 10} width="12" height="2" />
                        <rect className="ln" x={x + 4} y={y + 15} width="8" height="2" />
                    </g>
                )
            })}
        </svg>
    )
}

/**
 * Progress through Add, Configure and Print. Every tile is a button that jumps to its step.
 * `sheets[i]` is how many of step i's three sheets are filled; `done[i]` shows a full stack.
 */
export default function Stepper({ current, sheets, done, onSelect }) {
    return (
        <nav className="n2p-steps" aria-label="Progress">
            {STEPS.map((step, i) => {
                const isCurrent = i === current
                const isDone = Boolean(done[i])
                return (
                    <button
                        key={step.key}
                        type="button"
                        className={`n2p-step${isDone ? ' is-done' : ''}`}
                        aria-current={isCurrent ? 'step' : undefined}
                        aria-label={`Step ${i + 1}, ${step.label}: ${step.name}${isDone ? ', done' : ''}`}
                        onClick={() => onSelect(i)}
                    >
                        <PaperStack filled={isDone ? 3 : sheets[i]} typing={isCurrent} />
                        <span>
                            <span className="n2p-step__num">{`0${i + 1} / ${step.label}`}</span>
                            <span className="n2p-step__name">{step.name}</span>
                        </span>
                    </button>
                )
            })}
        </nav>
    )
}
