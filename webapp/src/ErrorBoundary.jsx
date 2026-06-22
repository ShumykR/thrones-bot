import React from 'react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ error, errorInfo });
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '20px', background: '#333', color: '#fff', height: '100vh', overflowY: 'auto' }}>
          <h2 style={{ color: '#ef4444' }}>Щось пішло не так 😢</h2>
          <p>Будь ласка, зробіть скріншот цієї помилки:</p>
          <pre style={{ background: '#000', padding: '10px', fontSize: '12px', whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
            {this.state.error && this.state.error.toString()}
          </pre>
          <pre style={{ background: '#111', padding: '10px', fontSize: '10px', whiteSpace: 'pre-wrap', wordWrap: 'break-word', marginTop: '10px' }}>
            {this.state.errorInfo && this.state.errorInfo.componentStack}
          </pre>
        </div>
      );
    }

    return this.props.children; 
  }
}
