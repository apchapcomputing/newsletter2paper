'use client'

import { useEffect, useState } from 'react';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Typography from '@mui/material/Typography';
import { flagEnabled, flagPayload, onFlags, track } from '../../lib/analytics';
import { useAuth } from '../../contexts/useAuth';

// A button for a feature that doesn't exist yet: clicks measure demand before it's built.
// Hidden unless the PostHog flag `fake-door-<feature with dashes>` is on. The flag's JSON
// payload can override the copy: { "label": "...", "description": "..." }.
export function fakeDoorFlag(feature) {
    return `fake-door-${feature.replaceAll('_', '-')}`;
}

export default function FakeDoor({ feature, label, description, sx }) {
    const { user } = useAuth();
    const flag = fakeDoorFlag(feature);
    const [visible, setVisible] = useState(false);
    const [payload, setPayload] = useState(null);
    const [open, setOpen] = useState(false);
    const [requested, setRequested] = useState(false);

    useEffect(() => onFlags(() => {
        setVisible(flagEnabled(flag));
        setPayload(flagPayload(flag));
    }), [flag]);

    if (!visible) return null;

    const handleClick = () => {
        track('fake_door_clicked', { feature, is_guest: !user });
        setOpen(true);
    };

    const handleRequest = () => {
        track('early_access_requested', { feature, is_guest: !user });
        setRequested(true);
    };

    const handleClose = () => {
        setOpen(false);
        setRequested(false);
    };

    return (
        <>
            <Button size="small" variant="text" onClick={handleClick} sx={{ textTransform: 'none', ...sx }}>
                {payload?.label || label}
            </Button>
            <Dialog open={open} onClose={handleClose} maxWidth="xs" fullWidth>
                <DialogTitle>Coming soon</DialogTitle>
                <DialogContent>
                    <Typography variant="body2">
                        {requested
                            ? (user
                                ? "Thanks! We'll let you know at your account email when it's ready."
                                : "Thanks! Sign in so we can let you know when it's ready.")
                            : (payload?.description || description || "We're deciding what to build next. Want early access?")}
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleClose}>{requested ? 'Close' : 'Not now'}</Button>
                    {!requested && (
                        <Button variant="contained" color="secondary" onClick={handleRequest}>
                            Yes, I want early access
                        </Button>
                    )}
                </DialogActions>
            </Dialog>
        </>
    );
}
