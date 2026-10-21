import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import ScheduleSettings from '@/app/components/ScheduleSettings'

const issue = (over = {}) => ({
    frequency: 'weekly', schedule_timezone: 'Europe/Berlin', schedule_time_local: '07:30:00',
    schedule_weekday: 0, schedule_day_of_month: null, ...over,
})

describe('ScheduleSettings', () => {
    it('renders nothing until the issue is loaded', () => {
        const { container } = render(<ScheduleSettings frequency="weekly" issue={null} onSave={vi.fn()} />)
        expect(container).toBeEmptyDOMElement()
    })

    it('summarises the stored schedule in words', () => {
        render(<ScheduleSettings frequency="weekly" issue={issue()} onSave={vi.fn()} />)
        expect(screen.getByText('Every Monday at 07:30 (Europe/Berlin)')).toBeInTheDocument()
        expect(screen.getByText(/restarts the countdown/)).toBeInTheDocument()
    })

    it('shows a weekday picker only for weekly, a day-of-month picker only for monthly, neither for daily', () => {
        const { rerender } = render(<ScheduleSettings frequency="weekly" issue={issue()} onSave={vi.fn()} />)
        expect(screen.getByLabelText('Day')).toBeInTheDocument()
        expect(screen.queryByLabelText('Day of month')).not.toBeInTheDocument()

        rerender(<ScheduleSettings frequency="monthly" issue={issue({ frequency: 'monthly', schedule_day_of_month: 31 })} onSave={vi.fn()} />)
        expect(screen.getByLabelText('Day of month')).toBeInTheDocument()
        expect(screen.queryByLabelText('Day')).not.toBeInTheDocument()
        expect(screen.getByText(/Shorter months send on their last day/)).toBeInTheDocument()

        rerender(<ScheduleSettings frequency="daily" issue={issue({ frequency: 'daily' })} onSave={vi.fn()} />)
        expect(screen.queryByLabelText('Day')).not.toBeInTheDocument()
        expect(screen.queryByLabelText('Day of month')).not.toBeInTheDocument()
        expect(screen.getByLabelText('Time')).toBeInTheDocument()
    })

    it('saves the new time as HH:MM', async () => {
        const onSave = vi.fn().mockResolvedValue({ error: null })
        render(<ScheduleSettings frequency="daily" issue={issue({ frequency: 'daily' })} onSave={onSave} />)
        fireEvent.change(screen.getByLabelText('Time'), { target: { value: '18:45' } })
        await waitFor(() => expect(onSave).toHaveBeenCalledWith({ schedule_time_local: '18:45' }))
    })

    it('ignores a cleared time field instead of saving an empty value', () => {
        const onSave = vi.fn()
        render(<ScheduleSettings frequency="daily" issue={issue({ frequency: 'daily' })} onSave={onSave} />)
        fireEvent.change(screen.getByLabelText('Time'), { target: { value: '' } })
        expect(onSave).not.toHaveBeenCalled()
    })

    it('says so when saving fails', async () => {
        const onSave = vi.fn().mockResolvedValue({ error: { message: 'boom' } })
        render(<ScheduleSettings frequency="daily" issue={issue({ frequency: 'daily' })} onSave={onSave} />)
        fireEvent.change(screen.getByLabelText('Time'), { target: { value: '18:45' } })
        expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't save the schedule")
    })
})
