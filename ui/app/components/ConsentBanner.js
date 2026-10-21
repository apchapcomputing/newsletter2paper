'use client'

import { useEffect, useState } from 'react';
import Snackbar from '@mui/material/Snackbar';
import SnackbarContent from '@mui/material/SnackbarContent';
import Button from '@mui/material/Button';
import { consent } from '../../lib/analytics';

// Fired by the footer's "Privacy choices" link to show the banner again.
export const OPEN_CONSENT_EVENT = 'n2p:open-consent';

export default function ConsentBanner() {
    const [open, setOpen] = useState(false);

    useEffect(() => {
        setOpen(consent.status() === 'pending');
        const reopen = () => setOpen(consent.status() !== null);
        window.addEventListener(OPEN_CONSENT_EVENT, reopen);
        return () => window.removeEventListener(OPEN_CONSENT_EVENT, reopen);
    }, []);

    const choose = (accept) => {
        if (accept) consent.accept();
        else consent.decline();
        setOpen(false);
    };

    return (
        <Snackbar open={open} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
            <SnackbarContent
                message="We use anonymous analytics to learn what's useful. May we remember this browser between visits?"
                action={
                    <>
                        <Button color="inherit" size="small" onClick={() => choose(false)}>Decline</Button>
                        <Button color="secondary" size="small" variant="contained" onClick={() => choose(true)}>Accept</Button>
                    </>
                }
            />
        </Snackbar>
    );
}
