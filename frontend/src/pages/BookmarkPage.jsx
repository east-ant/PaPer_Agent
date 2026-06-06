import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Loader2, CheckCircle2, XCircle } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'https://paper-agent-altv.onrender.com'

export default function BookmarkPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [status, setStatus] = useState('loading') // 'loading', 'success', 'error'
  const [message, setMessage] = useState('북마크 저장 중...')

  useEffect(() => {
    async function saveBookmark() {
      const id = searchParams.get('id')
      const title = searchParams.get('title')
      const link = searchParams.get('link')
      const source = searchParams.get('source') || 'email'
      const summary = searchParams.get('summary') || ''
      const authors = searchParams.get('authors') || ''
      const citations = parseInt(searchParams.get('citations') || '0', 10)

      if (!id) {
        setStatus('error')
        setMessage('잘못된 요청입니다.')
        setTimeout(() => navigate('/dashboard'), 2000)
        return
      }

      const token = localStorage.getItem('token') || localStorage.getItem('ppa_token')
      if (!token) {
        // 토큰이 없으면 로그인 페이지로 이동, 로그인 후 다시 돌아오도록 설정 가능
        alert('로그인이 필요합니다.')
        navigate('/login')
        return
      }

      try {
        const res = await fetch(`${API_BASE}/api/storage_box/bookmark`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({
            paper_id: id,
            title: title || '제목 없음',
            summary: summary,
            link: link || '',
            source: source,
            authors: authors,
            citations: isNaN(citations) ? 0 : citations
          })
        })
        const data = await res.json()
        if (data.ok) {
          setStatus('success')
          setMessage(data.message || '북마크가 저장되었습니다!')
        } else {
          setStatus('error')
          setMessage(data.message || '저장에 실패했습니다.')
        }
      } catch (err) {
        setStatus('error')
        setMessage('서버 오류가 발생했습니다.')
      }

      setTimeout(() => navigate('/dashboard'), 2000)
    }

    saveBookmark()
  }, [searchParams, navigate])

  return (
    <div className="flex h-screen w-full flex-col items-center justify-center p-4">
      <div className="flex flex-col items-center rounded-2xl bg-white p-8 text-center shadow-lg">
        {status === 'loading' && (
          <>
            <Loader2 className="mb-4 h-12 w-12 animate-spin text-blue-500" />
            <h2 className="text-xl font-semibold text-gray-800">{message}</h2>
            <p className="mt-2 text-sm text-gray-500">잠시만 기다려주세요...</p>
          </>
        )}
        {status === 'success' && (
          <>
            <CheckCircle2 className="mb-4 h-12 w-12 text-green-500" />
            <h2 className="text-xl font-semibold text-gray-800">{message}</h2>
            <p className="mt-2 text-sm text-gray-500">곧 대시보드로 이동합니다.</p>
          </>
        )}
        {status === 'error' && (
          <>
            <XCircle className="mb-4 h-12 w-12 text-red-500" />
            <h2 className="text-xl font-semibold text-gray-800">{message}</h2>
            <p className="mt-2 text-sm text-gray-500">대시보드로 이동합니다.</p>
          </>
        )}
      </div>
    </div>
  )
}
