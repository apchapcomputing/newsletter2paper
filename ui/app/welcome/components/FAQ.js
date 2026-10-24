const FAQ_LIST = [
  ['Do I need an account?', 'No. One-off PDFs work without one. You only need an account to save your newspaper or to set up automated delivery.'],
  ['How does the weekly delivery work?', 'On the schedule you choose, we build a new edition from the articles published since the last one and email you a link to the PDF. You print it when you want to read.'],
  ['What about paywalled posts?', 'We read the public feed, so a paywalled post prints only what the publisher shares there, usually a preview. Support for subscriber-only content is on the roadmap.'],
  ['Do I need a printer?', 'Any printer works, and so does a print shop or library. The PDF is laid out for standard paper.'],
  ['Which newsletters work?', 'Substack newsletters and any site with an RSS or Atom feed. Search by name or paste the feed address.'],
]

export default function FAQ() {
  return (
    <section id="faq" className="lp-wrap lp-section">
      <p className="lp-label lp-muted" style={{ textAlign: 'center' }}>FAQ</p>
      <h2 className="lp-h2" style={{ textAlign: 'center' }}>Questions, answered.</h2>
      <div className="lp-faq">
        {FAQ_LIST.map(([q, a]) => (
          <details key={q}><summary>{q}</summary><p>{a}</p></details>
        ))}
      </div>
    </section>
  )
}
