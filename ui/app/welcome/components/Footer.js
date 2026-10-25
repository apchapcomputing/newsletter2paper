'use client'

import { OPEN_CONSENT_EVENT } from '../../components/ConsentBanner'
import { Logo } from './Header'

const FEATURE_REQUEST = 'https://docs.google.com/forms/d/e/1FAIpQLScqMWrxF2SikunyJhR2VXkw2xfYAb950DT2bu0J8KtaTkcY7g/viewform?usp=sharing&ouid=112836351698515957727'

export default function Footer() {
  return (
    <footer className="lp-wrap lp-foot">
      <div className="lp-foot__row">
        <Logo />
        <div className="lp-foot__links">
          <a href={FEATURE_REQUEST} target="_blank" rel="noopener noreferrer">Feature request</a>
          <button type="button" onClick={() => window.dispatchEvent(new Event(OPEN_CONSENT_EVENT))}>Privacy choices</button>
        </div>
        <span>A Minimap Studio app</span>
      </div>
    </footer>
  )
}
