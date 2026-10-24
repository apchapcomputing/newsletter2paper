// With/Without (ShipFast's pattern): the pain on the left, the fix on the right, line for line.
const WITHOUT = [
  'Read in the same app that sends everything else',
  'Skim, then lose the tab',
  'Cannot underline, circle or fold the corner',
  'Fifteen newsletters, fifteen notifications',
  'Eyes tired by the end of the day',
]
const WITH = [
  'Read away from the device that distracts you',
  'One edition, start to finish',
  'Pen in hand, margins to write in',
  'One document, when you decide to read',
  'Paper, a chair and an hour',
]

const Column = ({ title, items, mark, className }) => (
  <div className={`lp-wow__col ${className}`}>
    <h3>{title}</h3>
    <ul>{items.map((item) => <li key={item}><b aria-hidden="true">{mark}</b>{item}</li>)}</ul>
  </div>
)

export default function WithWithout() {
  return (
    <section className="lp-wrap lp-section">
      <h2 className="lp-h2">Same writers. Different afternoon.</h2>
      <div className="lp-wow">
        <Column title="Reading on a screen" items={WITHOUT} mark="✕" className="lp-wow__col--without" />
        <Column title="Reading on paper" items={WITH} mark="✓" className="lp-wow__col--with" />
      </div>
    </section>
  )
}
