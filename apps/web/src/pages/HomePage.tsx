import { Link } from 'react-router-dom'

export function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-16">
        <div className="text-center">
          <h1 className="text-5xl font-bold text-gray-900 mb-4">
            Wintern
          </h1>
          <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
            AI-powered web research agents that periodically search the web for content
            matching your interests and deliver curated digests.
          </p>

          <div className="flex justify-center space-x-4">
            <Link
              to="/health"
              className="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors"
            >
              Check System Health
            </Link>
          </div>
        </div>

        <div className="mt-16 grid md:grid-cols-3 gap-8 max-w-4xl mx-auto">
          <div className="bg-white rounded-lg p-6 shadow-md">
            <div className="text-3xl mb-4">🔍</div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Interpret
            </h3>
            <p className="text-gray-600">
              AI analyzes your research context and objectives to understand what you need.
            </p>
          </div>

          <div className="bg-white rounded-lg p-6 shadow-md">
            <div className="text-3xl mb-4">📊</div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Curate
            </h3>
            <p className="text-gray-600">
              Content is scored and filtered for relevance using intelligent curation.
            </p>
          </div>

          <div className="bg-white rounded-lg p-6 shadow-md">
            <div className="text-3xl mb-4">📬</div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Deliver
            </h3>
            <p className="text-gray-600">
              Receive personalized digests via Slack or email on your schedule.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
