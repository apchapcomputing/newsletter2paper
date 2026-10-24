'use client'

import { useState } from 'react'

import AuthModal from '../components/AuthModal'
import { track } from '../../lib/analytics'

import Header from './components/Header'
import Hero from './components/Hero'
import Problem from './components/Problem'
import HowItWorks from './components/HowItWorks'
import Features from './components/Features'
import WithWithout from './components/WithWithout'
import Pricing from './components/Pricing'
import FAQ from './components/FAQ'
import CTA from './components/CTA'
import Footer from './components/Footer'

// Section order follows ShipFast's landing page (Hero, Problem, Features, With/Without,
// Pricing, FAQ, CTA) with a How-it-works strip from the design mockup. Styling is the
// design system's paper-and-ink look (landing.css). Copy follows marketing/messaging.md.
export default function Landing({ samples, photos, heroImage }) {
  const [authOpen, setAuthOpen] = useState(false)

  const onCta = (location) => track('landing_cta_clicked', { location, target: 'app' })
  const onPaid = () => {
    track('landing_cta_clicked', { location: 'pricing_paid', target: 'signup' })
    setAuthOpen(true)
  }

  return (
    <>
      <Header />
      <main>
        <Hero onCta={onCta} heroImage={heroImage} />
        <Problem />
        <HowItWorks />
        <Features
          samples={samples}
          photos={photos}
          onSampleDownload={(sample) => track('sample_pdf_downloaded', { sample })}
        />
        <WithWithout />
        <Pricing onFree={() => onCta('pricing_free')} onPaid={onPaid} />
        <FAQ />
        <CTA onCta={onCta} />
      </main>
      <Footer />
      <AuthModal open={authOpen} onClose={() => setAuthOpen(false)} trigger="landing" />
    </>
  )
}
