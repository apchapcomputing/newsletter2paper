'use client'

import { useState } from 'react'
import { Box, Typography, Button, Checkbox, FormControlLabel, Tooltip } from '@mui/material'
import { useSelectedPublications } from '../../contexts/useSelectedPublications'
import { useNewsletterConfig } from '../../contexts/useNewsletterConfig'
import AddUrlModal from './AddUrlModal'

export default function AddPublications({ onOpenSearch }) {
    const { selectedPublications, removePublication, toggleRemoveImages } = useSelectedPublications()
    const { outputMode } = useNewsletterConfig()
    const [isUrlModalOpen, setIsUrlModalOpen] = useState(false)

    // Only show remove images option for essay format
    const showImageOptions = outputMode === 'essay'

    // Handle master checkbox to toggle all publications
    const handleToggleAllImages = (event) => {
        const isChecked = event.target.checked
        selectedPublications.forEach(pub => {
            const currentState = pub.remove_images || false
            // Only toggle if the current state is different from target state
            if (currentState !== isChecked) {
                toggleRemoveImages(pub.id || pub.name)
            }
        })
    }

    // Check if all publications have remove_images enabled
    const allImagesRemoved = selectedPublications.length > 0 &&
        selectedPublications.every(pub => pub.remove_images === true)

    // Check if some (but not all) have remove_images enabled
    const someImagesRemoved = selectedPublications.some(pub => pub.remove_images === true) && !allImagesRemoved

    return (
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
                Add Publications
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
                Add Substack publications to print in your newspaper
            </Typography>

            <Box sx={{
                width: '100%',
                height: '2px',
                backgroundColor: 'var(--black)',
                mb: 3
            }} />

            {/* Add Publication Source Controls */}
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mb: 3 }}>
                <Typography variant="body1" sx={{ fontWeight: 500 }}>
                    ADD PUBLICATION SOURCE
                </Typography>
                <Box sx={{ display: 'flex', gap: 2, flexDirection: { xs: 'column', sm: 'row' } }}>
                    <Button
                        variant="contained"
                        onClick={onOpenSearch}
                        sx={{
                            flex: 1,
                            py: 1.5,
                            fontWeight: 'medium',
                            textTransform: 'none',
                            fontSize: '1rem',
                            backgroundColor: '#f5f5f5',
                            color: '#291D18',
                            border: '1px solid #ccc',
                            '&:hover': {
                                borderColor: '#291D18'
                            }
                        }}
                    >
                        SEARCH
                    </Button>
                    <Button
                        variant="contained"
                        onClick={() => setIsUrlModalOpen(true)}
                        sx={{
                            flex: 1,
                            py: 1.5,
                            fontWeight: 'medium',
                            textTransform: 'none',
                            fontSize: '1rem',
                            backgroundColor: '#f5f5f5',
                            color: '#291D18',
                            border: '1px solid #ccc',
                            '&:hover': {
                                borderColor: '#291D18'
                            }
                        }}
                    >
                        ADD VIA URL
                    </Button>
                </Box>
            </Box>

            {/* Publications to Print */}
            <Box>
                <Typography variant="body1" sx={{ fontWeight: 500, mb: 2 }}>
                    PUBLICATIONS TO PRINT
                </Typography>

                {/* Master checkbox to toggle all (only show if there are publications and essay mode) */}
                {showImageOptions && selectedPublications.length > 0 && (
                    <Box sx={{ mb: 2, pl: 1 }}>
                        <Tooltip
                            title="Toggle image removal for all publications at once. You can then adjust individual publications as needed."
                            placement="right"
                        >
                            <FormControlLabel
                                control={
                                    <Checkbox
                                        checked={allImagesRemoved}
                                        indeterminate={someImagesRemoved}
                                        onChange={handleToggleAllImages}
                                        size="small"
                                        sx={{
                                            color: 'var(--primary)',
                                            '&.Mui-checked': {
                                                color: 'var(--primary)',
                                            },
                                            '&.MuiCheckbox-indeterminate': {
                                                color: 'var(--primary)',
                                            },
                                        }}
                                    />
                                }
                                label={
                                    <Typography variant="body2" sx={{ fontSize: '0.875rem', fontWeight: 500 }}>
                                        Remove images from all publications
                                    </Typography>
                                }
                            />
                        </Tooltip>
                    </Box>
                )}

                {/* Selected Publications List */}
                {selectedPublications.length > 0 ? (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                        {selectedPublications.map((publication, index) => (
                            <Box
                                key={publication.id || index}
                                sx={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    p: 2,
                                    backgroundColor: '#f5f5f5',
                                    border: '1px solid #ccc'
                                }}
                            >
                                {/* Publication Header with Title and Remove Button */}
                                <Box sx={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'flex-start',
                                    mb: showImageOptions ? 1 : 0
                                }}>
                                    <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
                                        <Typography variant="body1" sx={{ fontWeight: 500 }}>
                                            {publication.name || publication.title}
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            {publication.publisher || publication.handle || publication.url}
                                        </Typography>
                                    </Box>
                                    <Button
                                        onClick={() => removePublication(publication.id || publication.name)}
                                        sx={{
                                            minWidth: 'auto',
                                            p: 1,
                                            color: 'text.secondary',
                                            '&:hover': {
                                                backgroundColor: 'transparent',
                                                color: 'error.main'
                                            }
                                        }}
                                    >
                                        ×
                                    </Button>
                                </Box>

                                {/* Image Options for Essay Format */}
                                {showImageOptions && (
                                    <Box sx={{ mt: 0.5 }}>
                                        <Tooltip
                                            title="When enabled, images from this publication will be removed from the PDF"
                                            placement="right"
                                        >
                                            <FormControlLabel
                                                control={
                                                    <Checkbox
                                                        checked={publication.remove_images || false}
                                                        onChange={() => toggleRemoveImages(publication.id || publication.name)}
                                                        size="small"
                                                        sx={{
                                                            color: 'var(--primary)',
                                                            '&.Mui-checked': {
                                                                color: 'var(--primary)',
                                                            },
                                                        }}
                                                    />
                                                }
                                                label={
                                                    <Typography variant="body2" sx={{ fontSize: '0.875rem' }}>
                                                        Remove images from this publication
                                                    </Typography>
                                                }
                                            />
                                        </Tooltip>
                                    </Box>
                                )}
                            </Box>
                        ))}
                    </Box>
                ) : (
                    <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                        No publications selected yet. Use the search or add URL options above to add publications.
                    </Typography>
                )}
            </Box>

            {/* Add URL Modal */}
            <AddUrlModal
                open={isUrlModalOpen}
                onClose={() => setIsUrlModalOpen(false)}
            />
        </Box>
    )
}