import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary]', error, info)
  }

  handleReset() {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <div
        style={{ background: 'var(--bg-primary)' }}
        className="flex min-h-screen flex-col items-center justify-center px-6"
      >
        <div className="animate-fade-up text-center">
          <p
            className="mb-2 text-5xl font-semibold"
            style={{ color: 'var(--text-primary)', opacity: 0.12, letterSpacing: '-0.03em' }}
          >
            오류
          </p>
          <p
            className="mb-1 text-xl font-normal"
            style={{ color: 'var(--text-primary)', letterSpacing: '-0.02em' }}
          >
            문제가 발생했습니다
          </p>
          <p className="mb-8 text-sm" style={{ color: 'var(--text-secondary)' }}>
            예상치 못한 오류가 발생했습니다. 다시 시도해주세요.
          </p>
          <div className="flex items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => this.handleReset()}
              className="inline-flex items-center rounded-xl px-5 py-2.5 text-sm font-medium transition-opacity hover:opacity-85"
              style={{ background: 'var(--bg-dark)', color: 'var(--text-on-dark)' }}
            >
              다시 시도
            </button>
            <button
              type="button"
              onClick={() => { window.location.href = '/dashboard' }}
              className="inline-flex items-center rounded-xl border px-5 py-2.5 text-sm font-medium transition-colors hover:border-gray-400"
              style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)', background: 'var(--bg-card)' }}
            >
              대시보드로
            </button>
          </div>
        </div>
      </div>
    )
  }
}
