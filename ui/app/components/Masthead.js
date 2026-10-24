// The nameplate: blackletter name between two ears that carry live facts about the paper,
// then the double rule. The masthead is the brand on the page, so there is no logo row above it.
export default function Masthead({ title, weekday, publicationCount, windowLabel }) {
    return (
        <>
            <header className="n2p-mast">
                <div className="n2p-ear">
                    <span className="n2p-label">Today&apos;s paper</span>
                    <span className="n2p-ear__big">{title || 'Untitled'}</span>
                    <span className="n2p-ear__sm">{weekday} edition</span>
                </div>
                <div className="n2p-mast__mid">
                    <h1 className="n2p-mast__name">The Newsletter<br />Printing Press</h1>
                    <div className="n2p-label n2p-mast__motto">Est. 2025 <b>•</b> Substack RSS to newspaper PDF</div>
                </div>
                <div className="n2p-ear n2p-ear--right">
                    <span className="n2p-label">This issue</span>
                    <span className="n2p-ear__big">{publicationCount} {publicationCount === 1 ? 'newsletter' : 'newsletters'}</span>
                    <span className="n2p-ear__sm">from {windowLabel}</span>
                </div>
            </header>
            <hr className="n2p-rule n2p-rule--double" />
        </>
    )
}
