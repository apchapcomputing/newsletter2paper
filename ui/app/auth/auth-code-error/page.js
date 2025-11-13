import Link from 'next/link'

export default function AuthCodeError() {
    return (
        <div className="min-h-screen flex flex-col items-center justify-center p-4">
            <div className="max-w-md w-full bg-white rounded-lg shadow-md p-6 text-center">
                <h1 className="text-2xl font-bold text-red-600 mb-4">Authentication Error</h1>
                <p className="text-gray-600 mb-6">
                    There was an error processing your authentication. This could be due to an expired or invalid link.
                </p>
                <div className="space-y-3">
                    <Link
                        href="/"
                        className="block w-full bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700 transition-colors"
                    >
                        Return to Home
                    </Link>
                    <p className="text-sm text-gray-500">
                        You can try signing in again from the home page.
                    </p>
                </div>
            </div>
        </div>
    )
}