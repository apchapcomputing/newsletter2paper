import Link from 'next/link'

export default function CTA({ onCta }) {
  return (
    <section className="lp-wrap" style={{ paddingBottom: 8 }}>
      <div className="lp-window lp-cta">
        <div className="lp-window__bar" aria-hidden="true"><i /><i /></div>
        <div className="lp-window__body">
          <h2 className="lp-h2">Put your reading list on paper.</h2>
          <p className="lp-muted">Add a newsletter, choose a format, and see your front page before you print.</p>
          <Link href="/" onClick={() => onCta('footer')} className="lp-btn lp-btn--fill">Make my first PDF</Link>
          <p className="lp-muted" style={{ fontSize: 14, marginTop: 14 }}>Free for one-off PDFs. No account needed.</p>
        </div>
      </div>
    </section>
  )
}
