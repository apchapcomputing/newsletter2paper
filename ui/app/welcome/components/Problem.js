// Problem agitation (ShipFast's pattern): never mentions the product, only the cost of not reading.
const STEPS = [
  { n: '01', text: 'Open the inbox to read one essay' },
  { n: '02', text: 'One quick check turns into an hour' },
  { n: '03', text: 'The essay is still unread' },
]

export default function Problem() {
  return (
    <section className="lp-band">
      <div className="lp-wrap lp-section">
        <h2 className="lp-h2">You opened your phone to read one essay.</h2>
        <p className="lp-lede">
          The writers you chose sit in your inbox next to everything else that wants your attention. Anyone watching, kids included, sees which one wins.
        </p>
        <div className="lp-band__steps">
          {STEPS.flatMap((s, i) => [
            i > 0 && <span key={`a${i}`} className="lp-band__arrow" aria-hidden="true">→</span>,
            <div key={s.n} className="lp-band__step"><span className="lp-label">{s.n}</span><p>{s.text}</p></div>,
          ])}
        </div>
      </div>
    </section>
  )
}
