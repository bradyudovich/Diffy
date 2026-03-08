import { Component, type ReactNode } from "react";
import type { HistoryEntry } from "../types";

interface Props {
  entry: HistoryEntry;
  tosUrl?: string;
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

/** Error Boundary wrapping DiffViewer. When the OpenAI data is empty or
 *  malformed and causes a render error, shows a graceful fallback instead
 *  of a blank accordion. */
export default class DiffViewerErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: { componentStack: string }) {
    console.error("[DiffViewerErrorBoundary] Render error:", error, info.componentStack);
  }

  componentDidUpdate(prevProps: Props) {
    // Reset the error state whenever a new entry is selected so the viewer
    // gets a fresh attempt rather than staying in the fallback state.
    if (prevProps.entry !== this.props.entry) {
      this.setState({ hasError: false });
    }
  }

  render() {
    if (this.state.hasError) {
      const { tosUrl } = this.props;
      return (
        <div className="rounded-xl border border-gray-200 bg-gray-50 shadow-sm px-4 py-6 text-center">
          <p className="text-sm text-gray-500 mb-2">
            Summary temporarily unavailable
          </p>
          {tosUrl ? (
            <a
              href={tosUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-indigo-600 hover:underline"
            >
              View raw changes
            </a>
          ) : (
            <span className="text-sm text-gray-400">View raw changes</span>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}
