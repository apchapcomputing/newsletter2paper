/**
 * Custom logger that only outputs in development mode
 * In production, all logging is suppressed
 */

const isDevelopment = process.env.NODE_ENV === 'development';

export const logger = {
    log: (...args) => {
        if (isDevelopment) {
            console.log(...args);
        }
    },

    error: (...args) => {
        if (isDevelopment) {
            console.error(...args);
        }
    },

    warn: (...args) => {
        if (isDevelopment) {
            logger.warn(...args);
        }
    },

    info: (...args) => {
        if (isDevelopment) {
            console.info(...args);
        }
    },

    debug: (...args) => {
        if (isDevelopment) {
            console.debug(...args);
        }
    }
};

export default logger;
