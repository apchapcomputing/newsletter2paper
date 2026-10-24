import Link from 'next/link'

// No price is shown until one is decided.
const FREE = ['As many one-off PDFs as you like', 'Newspaper and essay layouts', 'No account needed']
const PAID = ['Everything in Free', 'Automated delivery to your inbox: daily, weekly or monthly', 'Coming soon: send individual articles from your reading list into your PDF']

const List = ({ items }) => <ul>{items.map((f) => <li key={f}><b aria-hidden="true">✓</b>{f}</li>)}</ul>

export default function Pricing({ onFree, onPaid }) {
  return (
    <section id="pricing" className="lp-sunk">
      <div className="lp-wrap lp-section">
        <p className="lp-label lp-muted">Pricing</p>
        <h2 className="lp-h2">Free to try, paid to put on autopilot.</h2>
        <div className="lp-plans">
          <div className="lp-plan">
            <h3>Free</h3>
            <p className="lp-muted">One-off PDFs, whenever you want one</p>
            <p className="lp-plan__price">$0</p>
            <List items={FREE} />
            <Link href="/" onClick={onFree} className="lp-btn lp-btn--fill">Make a PDF</Link>
          </div>
          <div className="lp-plan lp-plan--hot">
            <span className="lp-sticker">Automated</span>
            <h3>Paid</h3>
            <p className="lp-muted">Let the paper find you</p>
            <p className="lp-plan__price lp-plan__price--text">Pricing announced at launch</p>
            <List items={PAID} />
            <button type="button" onClick={onPaid} className="lp-btn">Create an account</button>
          </div>
        </div>
      </div>
    </section>
  )
}
