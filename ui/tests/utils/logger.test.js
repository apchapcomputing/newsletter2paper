import { describe, it, expect, vi, beforeEach } from 'vitest'

async function loadLogger(nodeEnv) {
    vi.stubEnv('NODE_ENV', nodeEnv)
    vi.resetModules()
    return (await import('@/utils/logger')).default
}

describe('logger', () => {
    beforeEach(() => {
        for (const m of ['log', 'error', 'warn', 'info', 'debug']) vi.spyOn(console, m).mockImplementation(() => {})
    })

    it.each(['log', 'error', 'warn', 'info', 'debug'])('forwards %s to the console in development', async (method) => {
        const logger = await loadLogger('development')
        logger[method]('a', { b: 1 })
        expect(console[method]).toHaveBeenCalledWith('a', { b: 1 })
    })

    it.each(['production', 'test'])('is silent outside development (%s), so user data in debug logs never reaches prod consoles', async (env) => {
        const logger = await loadLogger(env)
        for (const m of ['log', 'error', 'warn', 'info', 'debug']) logger[m]('secret')
        for (const m of ['log', 'error', 'warn', 'info', 'debug']) expect(console[m]).not.toHaveBeenCalled()
    })
})
