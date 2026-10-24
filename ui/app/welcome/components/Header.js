import Link from 'next/link'

export function Logo({ href = '/welcome' }) {
  return <Link href={href} className="lp-logo">newsletter<b>2</b>paper</Link>
}

export default function Header() {
  return (
    <header className="lp-wrap lp-head">
      <div className="lp-head__row">
        <Logo />
        <nav className="lp-nav" aria-label="Main">
          <a href="#how-it-works">How it works</a>
          <a href="#pricing">Pricing</a>
          <a href="#faq">FAQ</a>
        </nav>
      </div>
      <div className="lp-rule2" />
    </header>
  )
}
