// ─── Error Boundary ───────────────────────────────────────────────
// Catches unhandled render errors and displays a recovery UI.
// Prevents the entire app from crashing on a single component failure.

import { Component, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Optional fallback UI. If not provided, uses default ErrorFallback. */
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log to console for debugging. In production, send to error reporting service.
    console.error("[ErrorBoundary] Caught error:", error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="h-screen flex items-center justify-center bg-vellum p-8">
          <div className="max-w-md w-full bg-sheet border border-rule rounded-md p-6 text-center">
            {/* Error icon */}
            <div className="mx-auto mb-4 w-10 h-10 rounded-full bg-redline-wash flex items-center justify-center">
              <svg className="w-5 h-5 text-redline" viewBox="0 0 20 20" fill="none">
                <path
                  d="M10 6v4m0 4h.01M10 18a8 8 0 100-16 8 8 0 000 16z"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>

            <h2 className="text-sm font-semibold text-ink mb-1">
              Something went wrong
            </h2>
            <p className="text-xs text-graphite mb-4">
              {this.state.error?.message ?? "An unexpected error occurred."}
            </p>

            <div className="flex justify-center gap-2">
              <button
                type="button"
                onClick={this.handleReset}
                className="px-3 py-1.5 text-xs font-medium text-ink bg-board hover:bg-rule border border-rule rounded transition-colors duration-100"
              >
                Try again
              </button>
              <button
                type="button"
                onClick={() => window.location.reload()}
                className="px-3 py-1.5 text-xs text-graphite hover:text-ink transition-colors duration-100"
              >
                Reload page
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
