'use client'

import { Box, Typography, Button, Collapse, Alert, AlertTitle, Link } from '@mui/material'
import { useState } from 'react'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
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
    const [showTroubleshoot, setShowTroubleshoot] = useState(false)

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

                {/* Success message after PDF generation */}
                {pdfUrl && (
                    <Box sx={{ mt: 3, display: 'flex', justifyContent: 'center' }}>
                        <Alert
                            sx={{
                                textAlign: 'left',
                                maxWidth: '500px',
                                backgroundColor: '#FFF4E6',
                                border: '1px solid #A44200',
                                color: '#291D18',
                                '& .MuiAlert-icon': {
                                    color: '#A44200'
                                }
                            }}
                        >
                            <AlertTitle sx={{ fontWeight: 600, color: '#A44200' }}>PDF Generated Successfully!</AlertTitle>
                            Your newspaper will open in a new tab automatically or visit{' '}
                            <Link
                                href={pdfUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                sx={{
                                    color: '#A44200',
                                    fontWeight: 600,
                                    textDecorationColor: '#A44200',
                                    '&:hover': {
                                        textDecorationThickness: '2px'
                                    }
                                }}
                            >
                                here
                            </Link>.

                            {/* Having trouble collapsible */}
                            <Box sx={{ mt: 2 }}>
                                <Button
                                    size="small"
                                    onClick={() => setShowTroubleshoot(!showTroubleshoot)}
                                    endIcon={showTroubleshoot ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                                    sx={{
                                        textTransform: 'none',
                                        fontSize: '0.875rem',
                                        p: 0,
                                        minWidth: 'auto',
                                        '&:hover': {
                                            backgroundColor: 'transparent',
                                        }
                                    }}
                                >
                                    Having trouble?
                                </Button>
                                <Collapse in={showTroubleshoot}>
                                    <Typography
                                        variant="body2"
                                        sx={{
                                            mt: 1,
                                            fontSize: '0.875rem'
                                        }}
                                    >
                                        Make sure you have enabled pop-up windows
                                    </Typography>
                                </Collapse>
                            </Box>
                        </Alert>
                    </Box>
                )}
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