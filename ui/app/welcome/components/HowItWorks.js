// Three-sheet stacks, the same paper icons the app's stepper uses, filling up per step.
function Stack({ filled }) {
  return (
    <svg className="lp-stack" viewBox="0 0 44 44" aria-hidden="true">
      {[2, 1, 0].map((i) => (
        <g key={i} className={i < filled ? 'is-filled' : ''}>
          <rect className="pg" x={4 + i * 6} y={12 - i * 5} width="22" height="26" />
          <rect className="ln" x={8 + i * 6} y={17 - i * 5} width="14" height="2" />
          <rect className="ln" x={8 + i * 6} y={22 - i * 5} width="10" height="2" />
        </g>
      ))}
    </svg>
  )
}

const STEPS = [
  { n: '01 / Add', title: 'Choose your newsletters', body: 'Search Substack or paste a feed link. Add every publication you want in this issue.' },
  { n: '02 / Configure', title: 'Set up your paper', body: 'Pick a format, name the paper, and choose how far back to pull articles.' },
  { n: '03 / Print', title: 'Print the issue', body: 'Preview your front page, make the PDF, then print it. Read with a pen in hand.' },
]

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="lp-sunk">
      <div className="lp-wrap lp-section">
        <p className="lp-label lp-muted">How it works</p>
        <h2 className="lp-h2">Three steps, one newspaper.</h2>
        <div className="lp-steps">
          {STEPS.map((s, i) => (
            <div key={s.n} className="lp-card">
              <Stack filled={i + 1} />
              <span className="lp-label">{s.n}</span>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
