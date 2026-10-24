import { OPEN_CONSENT_EVENT } from './ConsentBanner';

const FEATURE_REQUEST_URL = 'https://docs.google.com/forms/d/e/1FAIpQLScqMWrxF2SikunyJhR2VXkw2xfYAb950DT2bu0J8KtaTkcY7g/viewform?usp=sharing&ouid=112836351698515957727';

export default function Footer() {
    return (
        <footer className="n2p-footer">
            <a href="https://ashlynchapman.com" target="_blank" rel="noopener noreferrer">Built by Ashlyn Chapman</a>
            <span className="n2p-footer__dot" aria-hidden="true">•</span>
            <a href={FEATURE_REQUEST_URL} target="_blank" rel="noopener noreferrer">Feature Request</a>
            <span className="n2p-footer__dot" aria-hidden="true">•</span>
            <button type="button" onClick={() => window.dispatchEvent(new Event(OPEN_CONSENT_EVENT))}>Privacy choices</button>
            <span className="n2p-footer__dot" aria-hidden="true">•</span>
            <span>A Minimap Studio app</span>
        </footer>
    );
}
