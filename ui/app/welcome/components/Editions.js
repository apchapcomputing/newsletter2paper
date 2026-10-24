// Illustrative stand-ins for a printed edition, used until real photos are added to
// ui/public/landing/. Markup only; the text is placeholder, not real articles.
export function FrontPage() {
  return (
    <figure>
      <div className="lp-sheet" aria-hidden="true">
        <div className="lp-sheet__name">The Morning News</div>
        <div className="lp-sheet__folio"><span>Sample issue</span><span>3 newsletters</span></div>
        <div className="lp-cols">
          <div className="lp-story lp-story--lead">
            <div className="lp-halftone" />
            <h3>The long read leads the page</h3>
            <div className="lp-story__by">By a writer you follow</div>
            <div className="lp-bars"><i /><i /><i /><i style={{ width: '70%' }} /></div>
          </div>
          <div className="lp-story">
            <h3>A second voice, a second column</h3>
            <div className="lp-bars"><i /><i /><i /><i /><i style={{ width: '60%' }} /></div>
            <h3>And a short one</h3>
            <div className="lp-bars"><i /><i /><i style={{ width: '50%' }} /></div>
          </div>
          <div className="lp-story">
            <h3>Third publication</h3>
            <div className="lp-bars"><i /><i /><i /><i style={{ width: '80%' }} /></div>
            <p className="lp-jump"><b>Continued on PAGE 2</b></p>
            <div className="lp-bars" style={{ marginTop: 8 }}><i /><i /><i style={{ width: '40%' }} /></div>
          </div>
        </div>
      </div>
      <figcaption className="lp-caption">Illustrative layout</figcaption>
    </figure>
  )
}

export function EssayPage() {
  return (
    <figure>
      <div className="lp-sheet lp-essay" aria-hidden="true">
        <div className="lp-sheet__name">The Morning News</div>
        <div className="lp-sheet__folio"><span>Essay</span><span>Page 1</span></div>
        <h3>One piece, one column, room for a pen</h3>
        <div className="lp-bars">{[...Array(11)].map((_, i) => <i key={i} style={i % 5 === 4 ? { width: '65%' } : undefined} />)}</div>
      </div>
      <figcaption className="lp-caption">Illustrative layout</figcaption>
    </figure>
  )
}

export function EmailCard() {
  return (
    <figure>
      <div className="lp-sheet" aria-hidden="true">
        <div className="lp-sheet__name">Your edition is ready</div>
        <div className="lp-sheet__folio"><span>Every Sunday</span><span>New since last week</span></div>
        <div className="lp-mail">
          <div className="lp-bars"><i style={{ width: '55%' }} /><i /><i style={{ width: '85%' }} /></div>
          <span className="lp-btn lp-btn--fill">Open this week&apos;s edition</span>
        </div>
      </div>
      <figcaption className="lp-caption">Illustrative email</figcaption>
    </figure>
  )
}
