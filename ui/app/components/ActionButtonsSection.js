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
    const { currentIssueId } = useNewsletterConfig()
    const { selectedPublications } = useSelectedPublications()

    return (
        <>
            {/* Action Buttons Section */}
            <Box sx={{
                display: 'flex',
                gap: 3,
                justifyContent: 'center',
                flexDirection: { xs: 'column', sm: 'row' },
                width: '100%',
                maxWidth: 600,
                mx: 'auto'
            }}>
                <Button
                    variant="contained"
                    onClick={onSaveIssue}
                    disabled={isSaving}
                    sx={{
                        flex: 1,
                        py: 2,
                        px: 4,
                        fontWeight: 600,
                        textTransform: 'none',
                        fontSize: '1.1rem',
                        backgroundColor: '#f5f5f5',
                        color: 'black',
                        border: '2px solid #ccc',
                        '&:hover': {
                            borderColor: 'black'
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
                    variant="contained"
                    onClick={onGeneratePdf}
                    disabled={isGeneratingPdf || !currentIssueId}
                    sx={{
                        flex: 1,
                        py: 2,
                        px: 4,
                        fontWeight: 600,
                        textTransform: 'none',
                        fontSize: '1.1rem',
                        backgroundColor: '#f5f5f5',
                        color: 'black',
                        border: '2px solid #ccc',
                        '&:hover': {
                            borderColor: 'black'
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

            {/* Status Messages */}
            {!currentIssueId && selectedPublications.length > 0 && (
                <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', mt: 2 }}>
                    💡 Save your newspaper first, then print your PDF
                </Typography>
            )}

            {currentIssueId && (
                <Typography variant="body2" color="success.main" sx={{ textAlign: 'center', mt: 2 }}>
                    ✅ Newspaper configuration saved! Ready to print
                </Typography>
            )}

            {/* Show PDF URL if available */}
            {pdfUrl && (
                <Box sx={{ mt: 3, p: 3, backgroundColor: '#e8f5e8', border: '1px solid #4caf50', textAlign: 'center' }}>
                    <Typography variant="body1" color="success.main" sx={{ mb: 2, fontWeight: 500 }}>
                        ✅ PDF generated successfully!
                    </Typography>
                    <Button
                        variant="outlined"
                        onClick={() => window.open(pdfUrl, '_blank')}
                        sx={{
                            textTransform: 'none',
                            fontWeight: 500,
                            borderColor: 'success.main',
                            color: 'success.main',
                            '&:hover': {
                                backgroundColor: 'success.light'
                            }
                        }}
                    >
                        📄 Open PDF
                    </Button>
                </Box>
            )}
        </>
    )
}