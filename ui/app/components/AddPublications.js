'use client'

import { useState } from 'react'
import { Box, Typography, Button } from '@mui/material'
import { useSelectedPublications } from '../../contexts/useSelectedPublications'
import AddUrlModal from './AddUrlModal'

export default function AddPublications({ onOpenSearch }) {
    const { selectedPublications, removePublication } = useSelectedPublications()
    const [isUrlModalOpen, setIsUrlModalOpen] = useState(false)

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

                {/* Selected Publications List */}
                {selectedPublications.length > 0 ? (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                        {selectedPublications.map((publication, index) => (
                            <Box
                                key={publication.id || index}
                                sx={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    p: 2,
                                    backgroundColor: '#f5f5f5',
                                    border: '1px solid #ccc'
                                }}
                            >
                                <Box sx={{ display: 'flex', flexDirection: 'column' }}>
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
                                            backgroundColor: 'primary'
                                        }
                                    }}
                                >
                                    ×
                                </Button>
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