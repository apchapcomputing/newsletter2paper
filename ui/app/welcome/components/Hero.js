import Link from 'next/link'
import { FrontPage } from './Editions'

export default function Hero({ onCta, heroImage }) {
  return (
    <section className="lp-wrap lp-hero">
      <div>
        <p className="lp-label lp-muted">Substack newsletters, printed</p>
        <h1 className="lp-h1">The reading you meant to do, on paper.</h1>
        <p className="lp-hero__sub">
          Pick the newsletters you love. We lay them out as a printable newspaper or essay, and can deliver a fresh edition every week. No scrolling, no inbox, no screen.
        </p>
        <div className="lp-hero__cta">
          <Link href="/" onClick={() => onCta('hero')} className="lp-btn lp-btn--fill">Try it free</Link>
          <a href="#how-it-works" className="lp-link">Continued below: how it works →</a>
        </div>
        <p className="lp-hero__note">Free for one-off PDFs. No account needed.</p>
      </div>
      <div>
        {heroImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={heroImage} alt="A newsletter2paper edition, printed and on a table" className="lp-hero__photo" />
        ) : (
          <FrontPage />
        )}
      </div>
    </section>
  )
}
