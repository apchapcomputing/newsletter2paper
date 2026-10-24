// At most one per view: the empty publication list, and the finished print.
export default function PullQuote({ quote, cite, children }) {
    return (
        <blockquote className="n2p-pull">
            <q>{quote}</q>
            {children}
            {cite && <cite>{cite}</cite>}
        </blockquote>
    )
}
