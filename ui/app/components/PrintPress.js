import { RegistrationMark } from './FrontPagePreview'

/**
 * The print button and its running state. While printing the key stays sunk, a registration
 * mark turns, halftone dots roll and "Stop the presses" appears. The status line is a live region.
 */
export default function PrintPress({ paperName, isPrinting, disabled, status, onPrint, onStop }) {
    return (
        <>
            <div className={`n2p-press${isPrinting ? ' is-printing' : ''}`}>
                <button
                    type="button"
                    className="n2p-print"
                    onClick={onPrint}
                    disabled={disabled || isPrinting}
                    aria-busy={isPrinting ? 'true' : undefined}
                >
                    <RegistrationMark className="n2p-reg" />
                    <span>{isPrinting ? `Printing ${paperName}…` : `Print ${paperName}`}</span>
                </button>
                <button type="button" className="n2p-btn n2p-btn--stop" onClick={onStop}>Stop the presses</button>
            </div>
            <p className="n2p-status" aria-live="polite">{status}</p>
        </>
    )
}
