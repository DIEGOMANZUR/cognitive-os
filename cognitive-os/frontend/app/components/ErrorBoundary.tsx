"use client";

import React from "react";

interface ErrorBoundaryProps {
  readonly children: React.ReactNode;
  readonly fallback?: (error: Error, reset: () => void) => React.ReactNode;
}

interface ErrorBoundaryState {
  readonly error: Error | null;
}

/**
 * Global error boundary so an exception inside any view does not blank the
 * entire cockpit. React's default behaviour is to unmount the whole subtree;
 * this catches that and renders a recoverable fallback with a reset button.
 */
export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    if (typeof console !== "undefined") {
      console.error("[ErrorBoundary]", error, info);
    }
  }

  private reset = (): void => {
    this.setState({ error: null });
  };

  override render(): React.ReactNode {
    if (this.state.error) {
      const { fallback } = this.props;
      if (fallback) return fallback(this.state.error, this.reset);
      return (
        <div className="section" role="alert" style={{ padding: "1rem", maxWidth: "60ch" }}>
          <h2>Algo falló en esta vista</h2>
          <p className="muted small" style={{ whiteSpace: "pre-wrap" }}>
            {this.state.error.message}
          </p>
          <p className="muted small">
            El cockpit se mantuvo arriba. Reintenta abajo o cambia de tab desde el sidebar.
          </p>
          <button type="button" className="primary" onClick={this.reset}>
            Reintentar
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
