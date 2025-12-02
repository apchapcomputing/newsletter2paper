'use client'

import { Box, Typography, Button } from '@mui/material'
import { useNewsletterConfig } from '../../contexts/useNewsletterConfig'
import { useSelectedPublications } from '../../contexts/useSelectedPublications'

export default function ActionButtonsSection({
    isSaving,
    isGeneratingPdf,
    pdfUrl,
    onGeneratePdf
}) {
    const { currentIssueId, newspaperTitle } = useNewsletterConfig()
    const { selectedPublications } = useSelectedPublications()

    return (
        <>
            {/* Section with Print button and PDF access */}
            <Box sx={{
                width: '100%',
                border: '2px solid black',
                p: 3,
                mb: 2
            }}>
                <Typography
                    variant="h4"
                    component="h2"
                    sx={{
                        textAlign: 'center',
                        fontWeight: 600,
                        mb: 1,
                        fontSize: { xs: '1.5rem', sm: '2rem' }
                    }}
                >
                    {pdfUrl ? 'Access Your Newspaper Issue' : 'Print Your Newspaper Issue'}
                </Typography>
                <Typography
                    variant="body2"
                    sx={{
                        textAlign: 'center',
                        fontStyle: 'italic',
                        color: 'text.secondary',
                        mb: 2
                    }}
                >
                    {pdfUrl ? 'Open or download your newspaper issue as a PDF' : 'Generate your newspaper as a PDF'}
                </Typography>

                <Box sx={{
                    width: '100%',
                    height: '2px',
                    backgroundColor: 'var(--black)',
                    mb: 3
                }} />

                <Box sx={{ display: 'flex', gap: 2, width: '100%', justifyContent: 'center' }}>
                    <Button
                        variant="outlined"
                        onClick={onGeneratePdf}
                        disabled={isGeneratingPdf || !currentIssueId}
                        sx={{
                            flex: 1,
                            maxWidth: '400px',
                            py: 2,
                            px: 4,
                            fontSize: '1rem',
                            backgroundColor: '#f5f5f5',
                            color: '#291D18',
                            border: '1px solid #ccc',
                            '&:hover': {
                                borderColor: '#291D18'
                            }
                        }}
                    >
                        {isGeneratingPdf ? `GENERATING ${newspaperTitle.toUpperCase()}...` : `PRINT ${newspaperTitle.toUpperCase()}`}
                    </Button>
                </Box>
            </Box >

            {/* Status Messages */}
            {
                !currentIssueId && selectedPublications.length > 0 && (
                    <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', mt: 2 }}>
                        💡 Your newspaper will auto-save, then you can print it
                    </Typography>
                )
            }
        </>
    )
}