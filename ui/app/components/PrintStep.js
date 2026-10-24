'use client'

import { useNewsletterConfig } from '../../contexts/useNewsletterConfig'
import { useSelectedPublications } from '../../contexts/useSelectedPublications'
import FakeDoor from './FakeDoor'
import FrontPagePreview from './FrontPagePreview'
import PrintPress from './PrintPress'
import PullQuote from './PullQuote'

// One story per newsletter: its newest article in the chosen window. Newsletters with nothing
// new are left off the page rather than invented.
export function frontPageStories(publications, previewFor) {
    return publications
        .map((publication) => {
            const article = previewFor(publication.id).articles[0]
            if (!article) return null
            return {
                headline: article.title,
                deck: article.subtitle,
                publication: publication.name || publication.title,
            }
        })
        .filter(Boolean)
}

export default function PrintStep({
    paperName,
    dateLabel,
    previewFor,
    isSaving,
    isGeneratingPdf,
    pdfUrl,
    printStatus,
    onGeneratePdf,
    onStopPrinting,
}) {
    const { currentIssueId } = useNewsletterConfig()
    const { selectedPublications } = useSelectedPublications()

    const stories = frontPageStories(selectedPublications, previewFor)
    const noPublications = selectedPublications.length === 0

    const status = isGeneratingPdf
        ? 'Setting type, inking the plates…'
        : printStatus
            || (noPublications ? 'Add at least one newsletter before printing.'
                : !currentIssueId ? 'Saving your paper, then you can print it.'
                    : isSaving ? 'Saving changes…' : '')

    return (
        <>
            <FrontPagePreview
                title={paperName}
                dateLabel={dateLabel}
                stories={stories}
                emptyMessage={noPublications
                    ? 'No stories yet. Go back to Add and choose a newsletter.'
                    : 'Nothing new in this window yet. Go back to Configure to widen it.'}
            />

            <PrintPress
                paperName={paperName}
                isPrinting={isGeneratingPdf}
                disabled={noPublications || !currentIssueId}
                status={status}
                onPrint={onGeneratePdf}
                onStop={onStopPrinting}
            />

            {pdfUrl && !isGeneratingPdf && (
                <PullQuote quote="Your inbox, finally on paper." cite={`${paperName} · printed just now`}>
                    <span className="n2p-pull__link">
                        Your paper opens in a new tab as a PDF. If nothing opened,{' '}
                        <a href={pdfUrl} target="_blank" rel="noopener noreferrer">open it here</a>
                        {' '}and check that pop-ups are allowed.
                    </span>
                </PullQuote>
            )}

            {/* Fake doors for ideas we haven't built; each is hidden until its PostHog flag is on. */}
            {pdfUrl && (
                <div style={{ marginTop: 'var(--space-4)', display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)', justifyContent: 'center' }}>
                    <FakeDoor feature="send_to_ereader" label="Send it to my Kindle or reMarkable" />
                    <FakeDoor feature="mail_printed_copy" label="Mail me a printed copy" />
                    <FakeDoor feature="single_article" label="Add a single article from a link" />
                </div>
            )}
        </>
    )
}
