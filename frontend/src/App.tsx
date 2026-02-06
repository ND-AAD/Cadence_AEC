import { useEffect, useState } from "react";

interface HealthStatus {
  status: string;
  service: string;
}

function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/v1/items/types")
      .then((res) => res.json())
      .then(() => {
        return fetch("/health");
      })
      .then((res) => res.json())
      .then((data) => setHealth(data))
      .catch((err) => setError(err.message));
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-cadence-700 mb-4">Cadence</h1>
        <p className="text-lg text-gray-600 mb-8">
          Three tables. One triple. Every story.
        </p>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 max-w-sm mx-auto">
          {error ? (
            <p className="text-red-500 text-sm">
              API not reachable — start with{" "}
              <code className="bg-gray-100 px-1 rounded">
                docker compose up
              </code>
            </p>
          ) : health ? (
            <p className="text-green-600 text-sm">
              Backend connected: {health.service} — {health.status}
            </p>
          ) : (
            <p className="text-gray-400 text-sm">Connecting to backend...</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
