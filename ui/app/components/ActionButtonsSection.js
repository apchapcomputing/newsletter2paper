'use client'

import { Box, Typography, Button } from '@mui/material'
import { useNewsletterConfig } from '../../contexts/useNewsletterConfig'
import { useSelectedPublications } from '../../contexts/useSelectedPublications'

export default function ActionButtonsSection({
    isSaving,
    isGeneratingPdf,
    pdfUrl,
    onSaveIssue,
    onGeneratePdf
}) {
    const { currentIssueId, newspaperTitle } = useNewsletterConfig()
    const { selectedPublications } = useSelectedPublications()

    return (
        <>
            {/* Save and Print buttons */}
            <Box sx={{
                display: 'flex',
                gap: 3,
                justifyContent: 'space-between',
                flexDirection: { xs: 'column', sm: 'row' },
                width: '100%',
            }}>
                <Button
                    variant="outlined"
                    onClick={onSaveIssue}
                    disabled={isSaving}
                    sx={{
                        flex: 1,
                        py: 2,
                        px: 4,
                        fontWeight: 500,
                        textTransform: 'none',
                        fontSize: '1rem',
                        color: 'var(--black)',
                        borderColor: 'var(--black)',
                        borderWidth: 2,
                        width: '100%',
                        '&:hover': {
                            borderColor: 'var(--black)',
                            backgroundColor: 'rgba(0, 0, 0, 0.04)'
                        },
                        '&:disabled': {
                            backgroundColor: '#d0d0d0',
                            color: '#666'
                        }
                    }}
                >
                    {isSaving ? 'SAVING...' : 'SAVE NEWSPAPER'}
                </Button>

                <Button
                    variant="outlined"
                    onClick={onGeneratePdf}
                    disabled={isGeneratingPdf || !currentIssueId}
                    sx={{
                        flex: 1,
                        py: 2,
                        px: 4,
                        fontWeight: 500,
                        textTransform: 'none',
                        fontSize: '1rem',
                        color: 'var(--black)',
                        borderColor: 'var(--black)',
                        borderWidth: 2,
                        width: '100%',
                        '&:hover': {
                            borderColor: 'var(--black)',
                            backgroundColor: 'rgba(0, 0, 0, 0.04)'
                        },
                        '&:disabled': {
                            backgroundColor: '#d0d0d0',
                            color: '#666'
                        }
                    }}
                >
                    {isGeneratingPdf ? 'GENERATING...' : 'PRINT NEWSPAPER'}
                </Button>
            </Box>

            {/* Final section with PDF access */}
            {(pdfUrl || currentIssueId) && (
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
                        Access Your Newspaper Issue
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
                        Open or download your newspaper issue as a PDF
                    </Typography>

                    <Box sx={{
                        width: '100%',
                        height: '2px',
                        backgroundColor: 'var(--black)',
                        mb: 3
                    }} />
                    <Typography variant="body1" sx={{ mb: 3, fontWeight: 500 }}>
                        {newspaperTitle.toUpperCase() || 'The Title of Your Newspaper'}
                    </Typography>

                    <Box sx={{ display: 'flex', gap: 2, width: '100%', justifyContent: 'space-between' }}>
                        <Button
                            variant="outlined"
                            onClick={() => pdfUrl && window.open(pdfUrl, '_blank')}
                            disabled={!pdfUrl}
                            sx={{
                                textTransform: 'none',
                                fontWeight: 500,
                                color: 'var(--black)',
                                borderColor: 'var(--black)',
                                borderWidth: 1,
                                px: 4,
                                py: 1.5,
                                width: '100%',
                                '&:hover': {
                                    borderColor: 'var(--black)',
                                    backgroundColor: 'rgba(0, 0, 0, 0.04)'
                                },
                                '&:disabled': {
                                    color: '#bdbdbd',
                                    borderColor: '#e0e0e0'
                                }
                            }}
                        >
                            OPEN URL
                        </Button>
                        <Button
                            variant="outlined"
                            onClick={() => pdfUrl && window.open(pdfUrl, '_blank')}
                            disabled={!pdfUrl}
                            sx={{
                                textTransform: 'none',
                                fontWeight: 500,
                                color: 'var(--black)',
                                borderColor: 'var(--black)',
                                borderWidth: 1,
                                px: 4,
                                py: 1.5,
                                width: '100%',
                                '&:hover': {
                                    borderColor: 'var(--black)',
                                    backgroundColor: 'rgba(0, 0, 0, 0.04)'
                                },
                                '&:disabled': {
                                    color: '#bdbdbd',
                                    borderColor: '#e0e0e0'
                                }
                            }}
                        >
                            DOWNLOAD FILE
                        </Button>
                    </Box>
                </Box>
            )}

            {/* Status Messages */}
            {!currentIssueId && selectedPublications.length > 0 && (
                <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', mt: 2 }}>
                    💡 Save your newspaper first, then print your PDF
                </Typography>
            )}
        </>
    )
}