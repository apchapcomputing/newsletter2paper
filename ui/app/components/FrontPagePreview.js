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
export default function FrontPagePreview({ title, dateLabel, stories, emptyMessage }) {
    const [lead, ...rest] = stories
    return (
        <div className="n2p-frontpage" role="img" aria-label={`Preview of the front page of ${title}`}>
            {['tl', 'tr', 'bl', 'br'].map((corner) => (
                <RegistrationMark key={corner} className={`n2p-frontpage__reg ${corner}`} />
            ))}
            <div className="n2p-frontpage__sheet" aria-hidden="true">
                <p className="n2p-frontpage__name">{title}</p>
                <div className="n2p-frontpage__folio">
                    <span>{dateLabel}</span>
                    <span>{stories.length} {stories.length === 1 ? 'story' : 'stories'}</span>
                </div>
                {lead ? (
                    <div className="n2p-cols">
                        <div className="n2p-story n2p-story--lead">
                            <div className="n2p-halftone" />
                            <h4>{lead.headline}</h4>
                            <p className="n2p-story__by">By {lead.publication}</p>
                            {lead.deck && <p className="n2p-dropcap">{lead.deck}</p>}
                        </div>
                        {rest.slice(0, 2).map((story) => (
                            <div className="n2p-story" key={story.publication}>
                                <h4>{story.headline}</h4>
                                <p className="n2p-story__by">By {story.publication}</p>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="n2p-help" style={{ textAlign: 'center' }}>{emptyMessage}</p>
                )}
            </div>
        </div>
    )
}
