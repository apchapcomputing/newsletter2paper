'use client'

import { useState } from 'react'
import { FrontPage, EssayPage, EmailCard } from './Editions'

const FEATURES = [
  {
    id: 'newspaper',
    title: 'A newspaper made from your subscriptions',
    description: 'Several publications on one multi-column front page, with the latest from each. Fold it, bring it to the table, mark it up.',
    Mock: FrontPage,
  },
  {
    id: 'essay',
    title: 'Or long-form, one essay at a time',
    description: 'Clean single-column pages for the pieces that deserve your full attention, with room in the margins for a pen.',
    Mock: EssayPage,
  },
  {
    id: 'delivery',
    title: 'A new issue in your inbox, on your schedule',
    description: 'Choose daily, weekly or monthly. We email a link to the latest issue, with only the articles published since the last one, so printing is the only step left. Automated delivery is part of the paid plan.',
    Mock: EmailCard,
  },
  {
    id: 'sources',
    title: 'Any Substack, any RSS feed',
    description: 'Search for a newsletter by name or paste a feed address. Mix publications freely in one issue.',
    Mock: FrontPage,
  },
]

export default function Features({ samples, photos, onSampleView }) {
  const [open, setOpen] = useState(FEATURES[0].id)
  const index = FEATURES.findIndex((f) => f.id === open)
  const { Mock, title } = FEATURES[index]
  const photo = photos[index]

  return (
    <section className="lp-wrap lp-section">
      <p className="lp-label lp-muted">What you get</p>
      <h2 className="lp-h2">A front page for your reading list.</h2>
      <div className="lp-feat">
        <ul className="lp-acc">
          {FEATURES.map((f, i) => (
            <li key={f.id}>
              <button type="button" aria-expanded={f.id === open} onClick={() => setOpen(f.id)}>
                <span className="lp-label">0{i + 1}</span>
                <span>{f.title}</span>
              </button>
              {f.id === open && <p>{f.description}</p>}
            </li>
          ))}
        </ul>
        <div className="lp-window">
          <div className="lp-window__bar" aria-hidden="true"><i /><i /></div>
          <div className="lp-window__body">
            {photo ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={photo} alt={title} loading="lazy" style={{ width: '100%', height: 'auto' }} />
            ) : (
              <Mock />
            )}
          </div>
        </div>
      </div>
      {samples.length > 0 && (
        <div className="lp-samples">
          {samples.map((s) => (
            <a key={s.id} href={s.href} target="_blank" rel="noopener noreferrer" onClick={() => onSampleView(s.id)} className="lp-btn">
              View a sample: {s.label}
            </a>
          ))}
        </div>
      )}
    </section>
  )
}
