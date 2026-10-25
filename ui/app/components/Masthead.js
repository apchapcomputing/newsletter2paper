// The nameplate: the blackletter name over the double rule. The masthead is the brand
// on the page, so there is no logo row above it. Facts about the current paper (title, count,
// window) live in the steps themselves, not repeated here.
export default function Masthead() {
    return (
        <>
            <header className="n2p-mast">
                <h1 className="n2p-mast__name">The Newsletter Printing Press</h1>
            </header>
            <hr className="n2p-rule n2p-rule--double" />
        </>
    )
}
