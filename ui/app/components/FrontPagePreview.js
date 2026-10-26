const REG_PATH = (
    <>
        <circle cx="12" cy="12" r="5.5" fill="none" stroke="currentColor" strokeWidth="2" />
        <path d="M12 1v22M1 12h22" stroke="currentColor" strokeWidth="2" />
        <path d="M12 6.5a5.5 5.5 0 0 1 5.5 5.5H12z" fill="currentColor" />
    </>
)

export function RegistrationMark({ className }) {
    return <svg className={className} viewBox="0 0 24 24" aria-hidden="true">{REG_PATH}</svg>
}

/**
 * A small front page of the issue, shown before printing: blackletter nameplate, folio strip,
 * columns with hairline rules, a drop cap on the lead and registration marks at the corners.
 * `stories` are `{ headline, deck?, publication }`, one per newsletter that has something to print.
 */
export default function FrontPagePreview({ title, dateLabel, stories, emptyMessage, format = 'newspaper' }) {
    const [lead, ...rest] = stories
    const isEssay = format === 'essay'
    const noun = isEssay ? ['piece', 'pieces'] : ['story', 'stories']
    return (
        <div className="n2p-frontpage" role="img" aria-label={`Preview of the ${isEssay ? 'opening page' : 'front page'} of ${title}`}>
            {['tl', 'tr', 'bl', 'br'].map((corner) => (
                <RegistrationMark key={corner} className={`n2p-frontpage__reg ${corner}`} />
            ))}
            <div className="n2p-frontpage__sheet" aria-hidden="true">
                <p className="n2p-frontpage__name">{title}</p>
                <div className="n2p-frontpage__folio">
                    <span>{dateLabel}</span>
                    <span>{isEssay && 'Essay · '}{stories.length} {stories.length === 1 ? noun[0] : noun[1]}</span>
                </div>
                {lead && isEssay ? (
                    <div className="n2p-essay">
                        <p className="n2p-story__by">By {lead.publication}</p>
                        <h4 className="n2p-essay__title">{lead.headline}</h4>
                        {lead.deck && <p className="n2p-dropcap n2p-essay__body">{lead.deck}</p>}
                        {rest.length > 0 && (
                            <p className="n2p-story__by">+ {rest.length} more {rest.length === 1 ? 'piece' : 'pieces'} to follow</p>
                        )}
                    </div>
                ) : lead ? (
                    <div className="n2p-cols">
                        <div className="n2p-story n2p-story--lead">
                            <div className="n2p-halftone" />
                            <h4>{lead.headline}</h4>
                            <p className="n2p-story__by">By {lead.publication}</p>
                            {lead.deck && <p className="n2p-dropcap">{lead.deck}</p>}
                        </div>
                        {rest.length > 0 && (
                            <div className="n2p-story-cols">
                                {rest.map((story, i) => (
                                    <div className="n2p-story" key={story.id || `${story.publication}-${i}`}>
                                        <h4>{story.headline}</h4>
                                        <p className="n2p-story__by">By {story.publication}</p>
                                        {story.deck && <p className="n2p-story__deck">{story.deck.length > 220 ? `${story.deck.slice(0, 220).trimEnd()}…` : story.deck}</p>}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                ) : (
                    <p className="n2p-help" style={{ textAlign: 'center' }}>{emptyMessage}</p>
                )}
            </div>
        </div>
    )
}
