// import { useMemo, useRef, useState } from 'react' // 기존
import { useEffect, useMemo, useRef, useState } from 'react' // #추가
import { useNavigate } from 'react-router-dom'
import { useAgentStore } from '../../store/agentStore'
import { X, Check, HelpCircle } from 'lucide-react'
import styles from './AgentStepper.module.css'

const MAX_KEYWORDS = 5
const steps = ['키워드', '소스', '표시항목', '알림', '요약']

const ALL_SOURCES = [
  { id: 'arxiv', label: 'arXiv', region: '해외', desc: '출판 전에 미리 공개되는 논문을 모아두는 곳이에요. AI·수학·과학 분야의 최신 연구를 가장 빠르게 받아볼 수 있어요.' },
  // { id: 'crossref', label: 'Crossref', region: '해외', desc: '학술지나 학회에 정식으로 실린 논문들을 모아둔 곳이에요. 검증된 연구 결과물을 찾을 때 좋아요.' },
  { id: 'semantic', label: 'Semantic Scholar', region: '해외', desc: '논문끼리 얼마나 많이 인용됐는지 분석해서 보여줘요. 주목받는 연구를 찾을 때 유용해요.' },
  // { id: 'core', label: 'CORE', region: '해외', desc: '무료로 전문을 읽을 수 있는 논문만 모아둔 곳이에요. 로그인 없이 바로 읽을 수 있는 논문들이에요.' },
]

const SUGGESTED_KEYWORDS = [
  'LLM', 'RAG', 'Transformer', 'Computer Vision',
  'Diffusion Model', 'Reinforcement Learning', 'NLP', 'GNN',
]

// summaryLength별 미리보기 텍스트 (백엔드 실제 요약 반환 전 mock)
const SUMMARY_PREVIEW = {
  short: '트랜스포머의 어텐션 메커니즘이 자연어 처리 성능을 획기적으로 향상시킨 연구입니다.',
  medium: '트랜스포머 기반 어텐션 메커니즘이 자연어 처리 성능을 기존 RNN 대비 크게 향상시켰습니다. 멀티헤드 어텐션과 포지셔널 인코딩을 결합해 병렬 처리 효율을 극대화했으며, GPT·BERT 등 대형 언어모델의 토대가 됩니다.',
  full: '트랜스포머는 순환 신경망(RNN)의 한계를 극복하기 위해 제안된 구조로, 셀프-어텐션 메커니즘을 통해 입력 시퀀스 전체를 동시에 처리합니다. 멀티헤드 어텐션은 다양한 표현 공간에서 정보를 병렬로 집계하며, 포지셔널 인코딩으로 순서 정보를 보완합니다. 이 설계는 학습 병렬화를 가능하게 해 훈련 속도를 대폭 높였고, GPT·BERT·T5 등 후속 대형 언어모델의 표준 아키텍처로 자리잡았습니다. 번역·요약·질의응답 등 거의 모든 NLP 태스크에서 기존 SOTA를 경신하며 딥러닝 패러다임을 전환한 역작입니다.',
}

export default function AgentStepper() {
  const navigate = useNavigate()
  const {
    agent,
    setAgent,
    connectNotification,
    disconnectNotification,
    testNotification,
    saveAgent,
    getDiscordChannels, // #기존 디스코드
    selectDiscordChannel, // #기존 디스코드 
    // getSlackChannels, // #slack 추가 (Slack 채널 목록 로드) 5/22
    // selectSlackChannel, // #slack 추가 (Slack 채널 저장) 5/22
  } = useAgentStore()
  const [step, setStep] = useState(1)
  const [keywordInput, setKeywordInput] = useState('')
  const [error, setError] = useState('')
  const [sourceFilter, setSourceFilter] = useState('전체')
  const [loading, setLoading] = useState(false)
  const [discordChannels, setDiscordChannels] = useState([]) // #추가
  const [selectedDiscordChannels, setSelectedDiscordChannels] = useState([]) // #추가
  // const [slackChannels, setSlackChannels] = useState([]) // #slack 추가 (Slack 채널 목록)
  // const [selectedSlackChannel, setSelectedSlackChannel] = useState('') // #slack 추가 (Slack 단일 선택)
  // const [selectedSlackWorkspaceId, setSelectedSlackWorkspaceId] = useState('') // #slack 추가 (Slack 워크스페이스 식별)
  const [savingChannel, setSavingChannel] = useState(false) // #추가
  const [channelAction, setChannelAction] = useState({ type: null, id: null }) // #추가

  // 취소 시 원복을 위한 마운트 시점 스냅샷
  const snapshot = useRef({
    ...agent,
    keywords: [...(agent.keywords ?? [])],
    sources:  [...(agent.sources ?? [])],
    notifications: {
      discord: { ...(agent.notifications?.discord ?? {}) },
      // slack:   { ...(agent.notifications?.slack ?? {}) },
      email:   { ...(agent.notifications?.email ?? {}) },
    },
  })

  const hasNotification = agent.notifications?.discord?.connected || /*agent.notifications?.slack?.connected ||*/ agent.notifications?.email?.connected

  useEffect(() => {
    async function loadChannels() {
      if (step !== 4) return

      if (agent.notifications?.discord?.connected) {
        const result = await getDiscordChannels()
        if (result?.ok) {
          const channels = Array.isArray(result.channels) ? result.channels : []
          setDiscordChannels(channels)
          if (result.discord_channel_ids) {
            setSelectedDiscordChannels(result.discord_channel_ids.map(String))
          } else if (result.selected_channel_id) {
            setSelectedDiscordChannels([String(result.selected_channel_id)])
          }
        }
      }

      // if (agent.notifications?.slack?.connected) {
      //   const result = await getSlackChannels() // #slack 추가 (Slack 연결 시 채널 목록 로드)
      //   if (result?.ok) {
      //     const channels = Array.isArray(result.channels) ? result.channels : []
      //     setSlackChannels(channels) // #slack 추가 (Slack 채널 목록 저장)
      //     const selected = result.selected || {}
      //     if (selected.channel_id) {
      //       setSelectedSlackChannel(String(selected.channel_id)) // #slack 추가 (선택된 Slack 채널 저장)
      //       setSelectedSlackWorkspaceId(String(selected.workspace_id || '')) // #slack 추가 (선택된 Slack 워크스페이스 저장)
      //     }
      //   }
      // }
    }
    loadChannels()
  }, [step, agent.notifications?.discord?.connected, /*agent.notifications?.slack?.connected,*/ getDiscordChannels/*, getSlackChannels*/]) // #추가

  // summaryLengthLabel 정의
  const summaryLengthLabel = useMemo(() => {
    if (agent.summaryLength === 'short') return '초록만'
    if (agent.summaryLength === 'full') return '전체'
    return '본문'
  }, [agent.summaryLength])

  // Step 1-3: 기본 핸들러들
  function addKeyword(event) {
    event.preventDefault()
    const next = keywordInput.trim()
    if (!next) return
    if (agent.keywords.length >= MAX_KEYWORDS) {
      setError('최대 5개까지 추가 가능합니다.')
      return
    }
    if (!agent.keywords.includes(next)) {
      setAgent({ keywords: [...agent.keywords, next] })
    }
    setKeywordInput('')
    setError('')
  }

  function addSuggestedKeyword(keyword) {
    if (agent.keywords.length >= MAX_KEYWORDS) {
      setError('최대 5개까지 추가 가능합니다.')
      return
    }
    if (!agent.keywords.includes(keyword)) {
      setAgent({ keywords: [...agent.keywords, keyword] })
    }
    setError('')
  }

  function removeKeyword(keyword) {
    setAgent({ keywords: agent.keywords.filter((item) => item !== keyword) })
    setError('')
  }

  function toggleSource(sourceId) {
    const next = agent.sources.includes(sourceId)
      ? agent.sources.filter((item) => item !== sourceId)
      : [...agent.sources, sourceId]
    setAgent({ sources: next })
  }

  function validate() {
    if (step === 1 && agent.keywords.length === 0) {
      setError('키워드를 최소 1개 이상 추가해주세요.')
      return false
    }
    if (step === 2 && agent.sources.length === 0) {
      setError('수집 소스를 최소 1개 이상 선택해주세요.')
      return false
    }
    setError('')
    return true
  }

  function next() {
    if (!validate()) return
    setStep((v) => Math.min(v + 1, 5))
  }

  function back() {
    setError('')
    setStep((v) => Math.max(v - 1, 1))
  }

  // 필터된 소스 목록 (Step 2 용)
  const visibleSources = sourceFilter === '전체'
    ? ALL_SOURCES
    : ALL_SOURCES.filter((s) => s.region === sourceFilter)

  // Discord 연결 핸들러
  async function handleConnect(channel) {
    // setLoading(true) // 기존
    setChannelAction({ type: 'connect', id: channel }) // #추가
    setError('')
    try {
      const result = await connectNotification(channel)
      if (!result || !result.ok) {
        const detail = result?.error ? `: ${result.error}` : '' // #추가
        const label = /*channel === 'slack' ? 'Slack' :*/ channel === 'discord' ? 'Discord' : channel
        setError((result?.message || `${label} 연결 실패`) + detail)
      }
    } catch (err) {
      setError('오류 발생: ' + err.message)
    } finally {
      // setLoading(false) // 기존
      setChannelAction({ type: null, id: null }) // #추가
    }
  }

  // 테스트 알림 핸들러
  async function handleTest(channel) {
    // setLoading(true) // 기존
    setChannelAction({ type: 'test', id: channel }) // #추가
    setError('')
    try {
      if (channel === 'discord' && selectedDiscordChannels.length === 0) {
        setError('채널을 먼저 선택해주세요.')
        return
      }
      // if (channel === 'slack' && !selectedSlackChannel) { // #slack 추가 (Slack 채널을 먼저 선택해야 테스트 가능)
      //   setError('Slack 채널을 먼저 선택해주세요.')
      //   return
      // }
      // const result = await testNotification(channel) // 기존
      let result = await testNotification(channel)
      if (!result || !result.ok) {
        const message = result?.message || ''

        // 채널 선택 정보가 없으면 OAuth 팝업을 다시 열어 선택 후 재시도
        if (channel === 'discord' && (message.includes('채널') || message.includes('선택'))) {
          const reconnect = await connectNotification('discord')
          if (reconnect?.ok || reconnect?.connected) {
            result = await testNotification(channel)
            if (result?.ok) {
              return
            }
          }
        }

        // if (channel === 'slack' && (message.includes('채널') || message.includes('선택'))) { // #slack 추가 (선택 채널이 없을 때 재연결 유도)
        //   const reconnect = await connectNotification('slack')
        //   if (reconnect?.ok || reconnect?.connected) {
        //     result = await testNotification(channel)
        //     if (result?.ok) {
        //       return
        //     }
        //   }
        // }

        const detail = result?.error ? `: ${result.error}` : '' // #추가
        setError((result?.message || '테스트 발송 실패') + detail)
      }
    } catch (err) {
      setError('오류 발생: ' + err.message)
    } finally {
      // setLoading(false) // 기존
      setChannelAction({ type: null, id: null }) // #추가
    }
  }

  async function handleDisconnect(channel) {
    setChannelAction({ type: 'disconnect', id: channel }) // #추가
    setError('')
    try {
      const result = await disconnectNotification(channel)
      if (!result?.ok) {
        const detail = result?.error ? `: ${result.error}` : ''
        setError((result?.message || '연결 해제 실패') + detail)
      }
    } catch (err) {
      setError('오류 발생: ' + err.message)
    } finally {
      setChannelAction({ type: null, id: null })
    }
  } // #추가

  async function handleDiscordChannelChange(id) {
    const channelId = String(id)
    setError('')

    const next = selectedDiscordChannels.includes(channelId)
      ? selectedDiscordChannels.filter(c => c !== channelId)
      : [...selectedDiscordChannels, channelId]

    setSelectedDiscordChannels(next)

    const selected = discordChannels.find((item) => String(item.channel_id) === channelId)
    if (!selected) return

    setSavingChannel(true)
    try {
      const saveResult = await selectDiscordChannel({
        guildId: String(selected.guild_id),
        channelId: next, // # 전체 리스트 전송
      })
      if (!saveResult?.ok) {
        setError(saveResult?.message || '채널 선택 저장 실패')
      }
    } finally {
      setSavingChannel(false)
    }
  }

  // async function handleSlackChannelChange(id) {
  //   const channelId = String(id)
  //   setError('')
  //
  //   const selected = slackChannels.find((item) => String(item.channel_id) === channelId)
  //   if (!selected) return
  //
  //   setSelectedSlackChannel(channelId) // #slack 추가 (Slack은 단일 채널만 저장)
  //   setSelectedSlackWorkspaceId(String(selected.workspace_id || '')) // #slack 추가 (워크스페이스 정보 저장)
  //
  //   setSavingChannel(true)
  //   try {
  //     const saveResult = await selectSlackChannel({
  //       workspaceId: String(selected.workspace_id || ''),
  //       channelId,
  //     })
  //     if (!saveResult?.ok) {
  //       setError(saveResult?.message || 'Slack 채널 선택 저장 실패')
  //     }
  //   } finally {
  //     setSavingChannel(false)
  //   }
  // }


  // 저장 핸들러
  async function handleSave() {
    const configured = agent.keywords.length > 0 && agent.sources.length > 0
    if (!configured) {
      setError('키워드, 소스 등 설정을 모두 입력해주세요.')
      return
    }

    setLoading(true)
    setError('')
    try {
      const result = await saveAgent({
        keywords: agent.keywords,
        sources: agent.sources,
        language: agent.language,
        summaryLength: agent.summaryLength,
        collectCount: agent.collectCount,
        frequency: agent.frequency,
      })
      if (result.ok) {
        // Discord로 즉시 발송됨 (backend 처리)
        setAgent({
          isConfigured: true,
          isActive: hasNotification,
        })
        navigate('/loading?next=/dashboard&mode=agent')
      } else {
        setError(result.message || '저장 실패')
      }
    } catch (err) {
      setError('오류 발생: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  function jumpTo(targetStep) {
    setError('')
    setStep(targetStep)
  }

  function save() {
    handleSave()
  }

  return (
    <div className={`animate-fade-up mx-auto w-full max-w-4xl rounded-xl ${styles.stepper}`}>
      {/* Header — step indicator */}
      <div className={`flex items-center justify-between px-5 py-3 ${styles.stepperHeader}`}>
        <div className="flex items-center gap-1.5">
          {steps.map((label, index) => {
            const num = index + 1
            const current = num === step
            const done = num < step
            return (
              <span
                key={label}
                className={`flex items-center gap-1 rounded px-2.5 py-1 text-xs font-medium ${current ? styles.stepCurrent : done ? styles.stepDone : styles.stepPending
                  }`}
              >
                {done ? <Check size={10} strokeWidth={2.5} /> : <span>{num}.</span>}
                {label}
              </span>
            )
          })}
        </div>
        <span className={`rounded px-2 py-1 text-xs tabular-nums ${styles.stepCounter}`}>
          {step} / 5
        </span>
      </div>

      {/* Body */}
      <div className="px-5 py-4">

        {/* ── Step 1: 키워드 ── */}
        {step === 1 && (
          <section>
            <p className={`mb-0.5 text-xs font-medium uppercase tracking-widest ${styles.stepLabel}`}>step 1</p>
            <p className={`mb-4 text-lg font-normal ${styles.stepTitle}`}>
              어떤 논문을 받을지 설정합니다
            </p>

            {/* 키워드 입력 */}
            <form onSubmit={addKeyword} className="mb-2">
              <input
                value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                placeholder="키워드 입력 후 Enter"
                className={`w-full max-w-lg rounded-lg px-3 py-2 text-sm outline-none transition-colors ${styles.keywordInput}`}
              />
            </form>

            <p className={`mb-2 text-xs ${styles.stepMeta}`}>
              키워드 ({agent.keywords.length}/{MAX_KEYWORDS}) · Enter로 추가
            </p>

            {/* 등록된 키워드 */}
            <div className="mb-4 flex flex-wrap gap-1.5">
              {agent.keywords.map((keyword) => (
                <span
                  key={keyword}
                  className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium ${styles.keywordTag}`}
                >
                  {keyword}
                  <button
                    type="button"
                    onClick={() => removeKeyword(keyword)}
                    className={styles.keywordTagRemove}
                  >
                    <X size={10} strokeWidth={2.5} />
                  </button>
                </span>
              ))}
              {agent.keywords.length === 0 && (
                <span className={`text-xs ${styles.keywordEmpty}`}>
                  아직 추가된 키워드가 없습니다.
                </span>
              )}
            </div>

            {/* 추천 키워드 */}
            <div>
              <p className={`mb-1.5 text-xs font-medium ${styles.stepMeta}`}>
                추천 키워드
              </p>
              <div className="flex flex-wrap gap-1.5">
                {SUGGESTED_KEYWORDS.map((kw) => {
                  const already = agent.keywords.includes(kw)
                  return (
                    <button
                      key={kw}
                      type="button"
                      onClick={() => !already && addSuggestedKeyword(kw)}
                      disabled={already}
                      className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${already ? styles.suggestBtnUsed : styles.suggestBtn
                        }`}
                    >
                      {already ? <Check size={9} className="mr-1 inline" strokeWidth={2.5} /> : '+ '}
                      {kw}
                    </button>
                  )
                })}
              </div>
            </div>

            <p className={`mt-3 text-xs ${styles.stepHint}`}>최대 5개</p>
          </section>
        )}

        {/* ── Step 2: 소스 ── */}
        {step === 2 && (
          <section>
            <p className={`mb-0.5 text-xs font-medium uppercase tracking-widest ${styles.stepLabel}`}>step 2</p>
            <p className={`mb-1 text-lg font-normal ${styles.stepTitle}`}>
              어디서 수집할지 선택합니다
            </p>
            <p className={`mb-4 text-xs leading-relaxed ${styles.stepMeta}`}>
              수집 기준: 최신 발행일순
            </p>

            {/* 전체/국내/해외 필터 */}
            <div className="mb-3 flex gap-1.5">
              {['전체', '해외'].map((label) => (
                <button
                  key={label}
                  onClick={() => setSourceFilter(label)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${sourceFilter === label ? styles.filterBtnActive : styles.filterBtnInactive
                    }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* 국내 소스 (준비중) */}
            {sourceFilter === '전체' && (
              <div className="mb-4">
                <p className={`mb-1.5 text-xs font-medium ${styles.stepMeta}`}>국내</p>
                <span className="inline-block rounded px-2.5 py-1.5 text-xs" style={{ background: 'var(--bg-secondary)', color: 'var(--text-muted)' }}>
                  준비중
                </span>
              </div>
            )}

            {/* 해외 소스 */}
            {(sourceFilter === '전체' || sourceFilter === '해외') && (
              <div className="mb-4">
                <p className={`mb-1.5 text-xs font-medium ${styles.stepMeta}`}>해외</p>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
                  {visibleSources.map((source) => {
                    const active = agent.sources.includes(source.id)
                    return (
                      <button
                        key={source.id}
                        onClick={() => toggleSource(source.id)}
                        className={`flex flex-col gap-2 rounded-xl p-3 text-left transition-all duration-150 ${active ? styles.sourceCardActive : styles.sourceCardInactive
                          }`}
                      >
                        <div className="flex items-center gap-1.5">
                          <span className={`text-sm font-medium ${active ? styles.sourceNameActive : styles.sourceNameInactive}`}>
                            {source.label}
                          </span>
                          <div
                            className="group/tip relative flex items-center"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <HelpCircle
                              size={13}
                              strokeWidth={1.75}
                              className={styles.sourceHelpIcon}
                              style={{ color: active ? 'rgba(255,255,255,0.4)' : undefined }}
                            />
                            <div className={`pointer-events-none absolute left-0 top-full z-30 mt-1.5 w-56 rounded-xl p-3 opacity-0 shadow-lg transition-all duration-150 group-hover/tip:pointer-events-auto group-hover/tip:opacity-100 ${styles.tooltip}`}>
                              <p className={`text-xs leading-relaxed ${styles.tooltipText}`}>
                                {source.desc}
                              </p>
                            </div>
                          </div>
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>
            )}

            {/* 논문 언어 */}
            <p className={`mb-1.5 text-xs font-medium ${styles.stepMeta}`}>요약 언어</p>
            <div className="flex gap-1.5">
              {[['ko', '한국어'], ['en', '영어'], ['all', '전체']].map(([value, label]) => {
                const active = agent.language === value
                return (
                  <button
                    key={value}
                    onClick={() => setAgent({ language: value })}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${active ? styles.filterBtnActive : styles.filterBtnInactive
                      }`}
                  >
                    {label}
                  </button>
                )
              })}
            </div>
          </section>
        )}

        {/* ── Step 3: 표시항목 ── */}
        {step === 3 && (
          <section>
            <p className={`mb-0.5 text-xs font-medium uppercase tracking-widest ${styles.stepLabel}`}>step 3</p>
            <p className={`mb-4 text-lg font-normal ${styles.stepTitle}`}>
              알림에 포함할 요약 범위를 정합니다
            </p>

            <p className={`mb-1.5 text-xs font-medium ${styles.stepMeta}`}>요약 범위</p>
            <div className="mb-4 flex gap-1.5">
              {[['short', '초록만', '2줄'], ['medium', '본문', '4~5줄'], ['full', '전체', '5줄+']].map(([value, label, hint]) => {
                const active = agent.summaryLength === value
                return (
                  <button
                    key={value}
                    onClick={() => setAgent({ summaryLength: value })}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${active ? styles.filterBtnActive : styles.filterBtnInactive
                      }`}
                  >
                    {label}
                    <span className="ml-1" style={{ opacity: 0.6, fontSize: '10px' }}>
                      ({hint})
                    </span>
                  </button>
                )
              })}
            </div>

            <p className={`mb-3 text-xs leading-relaxed ${styles.stepMeta}`}>
              기본 포함 항목: 논문 제목 · 저자 · 발행일 · 키워드 태그 · 저널명 · 논문요약 · 원문링크 · 수집날짜
            </p>

            {/* 미리보기 — summaryLength에 따라 요약 텍스트 변경 */}
            <div className={`rounded-lg p-3 ${styles.previewBox}`}>
              <p className={`mb-2 text-xs font-medium ${styles.previewTitle}`}>
                미리보기 — 알림 메시지 샘플
              </p>
              <p className={`text-xs font-medium ${styles.previewTitle}`}>
                Attention Is All You Need: A Survey on Transformer Architectures
              </p>
              <p className={`mt-0.5 text-xs ${styles.previewMeta}`}>
                Vaswani et al. · 2024.04.21 · LLM · Transformer · NEW
              </p>
              <p className={`mt-1 text-xs leading-relaxed ${styles.previewSummary}`}>
                {SUMMARY_PREVIEW[agent.summaryLength]}
              </p>
              <p className={`mt-1.5 text-xs ${styles.previewFooter}`}>
                인용 1,204 · 수집 2024.04.22 · arXiv ↗
              </p>
              <p className={`mt-1 text-xs font-medium ${styles.previewAccent}`}>
                요약범위: {summaryLengthLabel}
              </p>
            </div>
          </section>
        )}

        {/* ── Step 4: 알림 ── */}
        {step === 4 && (
          <section>
            <p className={`mb-0.5 text-xs font-medium uppercase tracking-widest ${styles.stepLabel}`}>step 4</p>
            <p className={`mb-4 text-lg font-normal ${styles.stepTitle}`}>
              어디로 받을지 정합니다
            </p>

            {/* 연동 가이드 */}
            <div className={`mb-4 rounded-lg p-3 ${styles.guideBox}`}>
              <p className={`mb-2 text-xs font-medium ${styles.guideLabel}`}>연동 방법</p>
              <ol className="space-y-1.5 text-xs">
                {[
                  <>아래 <strong>연결하기</strong> 버튼 클릭</>,
                  <>OAuth 창에서 <strong>허용(Authorize)</strong> 클릭</>,
                  <><strong>테스트 알림 전송</strong>으로 수신 확인</>,
                ].map((content, i) => (
                  <li key={i} className={`flex items-start gap-2 ${styles.guideStep}`}>
                    <span className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded text-white ${styles.guideStepNum}`} style={{ fontSize: '10px', fontWeight: 600 }}>
                      {i + 1}
                    </span>
                    {content}
                  </li>
                ))}
              </ol>
            </div>

            {/* 채널 카드 */}
            <div className="mb-4 space-y-2">
              {[
                { id: 'discord', label: 'Discord', desc: '서버 채널로 알림을 받습니다.' },
                // { id: 'slack',   label: 'Slack',   desc: '워크스페이스 채널로 알림을 받습니다.' },
                { id: 'email',   label: '이메일',  desc: '가입한 이메일 주소로 알림을 받습니다.' },
              ].map(({ id, label, desc }) => {
                const ch = agent.notifications?.[id] ?? { connected: false, lastTestStatus: null, lastTestAt: null }
                return (
                  <div
                    key={id}
                    className={`rounded-lg p-3 transition-colors ${ch.connected ? styles.channelCardConnected : styles.channelCardDefault}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className={`text-sm font-medium ${styles.channelName}`}>{label}</p>
                        <p className={`text-xs ${styles.channelDesc}`}>{desc}</p>
                        {id === 'discord' && ch.connected && (
                            <div className="mt-2 flex flex-wrap gap-1.5">
                              {discordChannels.length === 0 ? (
                                <p className="text-xs text-gray-500">채널을 불러오는 중이거나 채널이 없습니다.</p>
                              ) : (
                                discordChannels.map((item) => {
                                  const itemValue = String(item.channel_id)
                                  const label = `${item.guild_name} / #${item.channel_name}`
                                  const active = selectedDiscordChannels.includes(itemValue)
                                  return (
                                    <button
                                      key={itemValue}
                                      onClick={() => handleDiscordChannelChange(itemValue)}
                                      disabled={loading || savingChannel}
                                      className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                                        active ? styles.filterBtnActive : styles.filterBtnInactive
                                      } ${loading || savingChannel ? 'opacity-50 cursor-not-allowed' : ''}`}
                                    >
                                      {label}
                                      {active && <Check size={11} className="ml-1.5 inline-block" />}
                                    </button>
                                  )
                                })
                              )}
                            </div>
                        )}
                        {/* #slack 주석처리 (Slack 채널 목록 렌더링)
                        {id === 'slack' && ch.connected && (
                            <div className="mt-2 flex flex-wrap gap-1.5">
                              {slackChannels.length === 0 ? (
                                <p className="text-xs text-gray-500">Slack 채널을 불러오는 중이거나 채널이 없습니다.</p>
                              ) : (
                                slackChannels.map((item) => {
                                  const itemValue = String(item.channel_id)
                                  const channelLabel = `#${item.channel_name}`
                                  const active = selectedSlackChannel === itemValue
                                  return (
                                    <button
                                      key={itemValue}
                                      onClick={() => handleSlackChannelChange(itemValue)}
                                      disabled={loading || savingChannel}
                                      className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                                        active ? styles.filterBtnActive : styles.filterBtnInactive
                                      } ${loading || savingChannel ? 'opacity-50 cursor-not-allowed' : ''}`}
                                    >
                                      {channelLabel}
                                      {active && <Check size={11} className="ml-1.5 inline-block" />}
                                    </button>
                                  )
                                })
                              )}
                            </div>
                        )}
                        */}
                        {ch.connected && ch.lastTestStatus === 'success' && (
                          <p className={`mt-1 text-xs font-medium ${styles.channelTestOk}`}>
                            ✓ 테스트 알림 전송됨
                          </p>
                        )}
                        {ch.connected && ch.lastTestStatus === 'fail' && (
                          <p className={`mt-1 text-xs font-medium ${styles.channelTestFail}`}>
                            전송 오류 — 다시 시도해주세요.
                          </p>
                        )}
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1.5">
                        <button
                          onClick={() => handleConnect(id)}
                          // disabled={loading || ch.connected} // 기존
                          disabled={(channelAction.id === id && channelAction.type === 'connect') || ch.connected} // #추가
                          className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${ch.connected ? styles.connectBtnConnected : styles.connectBtnDefault
                            } ${((channelAction.id === id && channelAction.type === 'connect') || ch.connected) ? 'opacity-50 cursor-not-allowed' : ''}`}
                        >
                          {/* {loading ? '연결 중...' : ch.connected ? '연결됨 ✓' : '연결하기'} 기존 */}
                          {(channelAction.id === id && channelAction.type === 'connect') ? '연결 중...' : ch.connected ? '연결됨 ✓' : '연결하기'} {/* #추가 */}
                        </button>
                        {ch.connected && (
                          <button
                            onClick={() => handleTest(id)}
                            disabled={(channelAction.id === id && channelAction.type === 'test') || (id === 'discord' && selectedDiscordChannels.length === 0) /*|| (id === 'slack' && !selectedSlackChannel)*/} // # slack 주석처리
                            className={`text-xs font-medium underline transition-colors ${styles.testBtn} ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
                          >
                            {(channelAction.id === id && channelAction.type === 'test') ? '전송 중...' : '테스트 알림 전송'} {/* #추가 */}
                          </button>
                        )}
                        {ch.connected && (
                          <button
                            // onClick={() => disconnectNotification(id)} // 기존
                            onClick={() => handleDisconnect(id)} // #추가
                            disabled={channelAction.id === id && channelAction.type === 'disconnect'}
                            className={`text-xs underline transition-colors ${styles.disconnectBtn} ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
                          >
                            {(channelAction.id === id && channelAction.type === 'disconnect') ? '해제 중...' : '연결 끊기'} {/* #추가 */}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* 수집 옵션 */}
            <div className="grid grid-cols-2 gap-3">
              <OptionGroup
                title="수집 주기"
                items={[['daily', '매일'], ['3days', '3일'], ['weekly', '주간']]}
                value={agent.frequency}
                onSelect={(v) => setAgent({ frequency: v })}
              />
              <div>
                <OptionGroup
                  title="수집 수"
                  items={[1, 3, 5, 10].map((v) => [v, String(v)])}
                  value={agent.collectCount}
                  onSelect={(v) => setAgent({ collectCount: v })}
                />
              </div>
            </div>
          </section>
        )}

        {/* ── Step 5: 요약 ── */}
        {step === 5 && (
          <section>
            <p className={`mb-0.5 text-xs font-medium uppercase tracking-widest ${styles.stepLabel}`}>step 5</p>
            <p className={`mb-4 text-lg font-normal ${styles.stepTitle}`}>
              설정 요약
            </p>
            <div className={`overflow-hidden rounded-lg ${styles.summaryTable}`}>
              {[
                { label: '키워드', value: agent.keywords.join(', ') || '—', edit: 1 },
                // P2-4: 내부 ID → 표시명으로 변환 (예: 'semantic' → 'Semantic Scholar')
                { label: '사이트', value: agent.sources.map((id) => ALL_SOURCES.find((s) => s.id === id)?.label ?? id).join(', ') || '—', edit: 2 },
                { label: '수집 기준', value: '최신순', edit: null },
                { label: '언어', value: agent.language === 'ko' ? '한국어' : agent.language === 'en' ? '영어' : '전체', edit: 2 },
                {
                  label: '알림',
                  value:
                    [
                      agent.notifications?.discord?.connected && `Discord (${selectedDiscordChannels.length}개 채널)`,
                      // agent.notifications?.slack?.connected && `Slack (${selectedSlackWorkspaceId ? `${selectedSlackWorkspaceId} / ` : ''}${selectedSlackChannel ? `#${selectedSlackChannel}` : '연결됨'})`,
                      agent.notifications?.email?.connected && '이메일',
                    ].filter(Boolean).join(' · ') || '미연결',
                  edit: 4,
                },
                { label: '수집 주기', value: agent.frequency === 'daily' ? '매일' : agent.frequency === '3days' ? '3일' : '주간', edit: 4 },
                { label: '수집 수', value: `${agent.collectCount}개`, edit: 4 },
                { label: '요약 범위', value: summaryLengthLabel, edit: 3 },
              ].map(({ label, value, edit }, i) => (
                <div
                  key={label}
                  className={`flex items-center gap-3 px-3 py-2.5 ${i > 0 ? styles.summaryRow : ''}`}
                >
                  <span className={`w-20 shrink-0 text-xs font-medium ${styles.summaryLabel}`}>
                    {label}
                  </span>
                  <span className={`flex-1 text-sm ${styles.summaryValue}`}>{value}</span>
                  {edit !== null && (
                    <button
                      onClick={() => jumpTo(edit)}
                      className={`text-xs font-medium underline transition-colors ${styles.summaryEditBtn}`}
                    >
                      수정
                    </button>
                  )}
                </div>
              ))}
            </div>
            {!hasNotification && (
              <p className={`mt-3 text-xs ${styles.warningText}`}>
                알림이 연결되지 않았습니다. 저장 시 에이전트가 일시정지 상태가 됩니다.
              </p>
            )}
          </section>
        )}
      </div>

      {/* 에러 메시지 */}
      {error && (
        <div className="mx-5 mb-1">
          <p className={`text-xs font-medium ${styles.errorText}`}>{error}</p>
        </div>
      )}
      {step === 4 && !hasNotification && (
        <div className="mx-5 mb-1">
          <p className={`text-xs ${styles.warningText}`}>
            알림이 연결되지 않으면 에이전트가 일시정지 상태가 됩니다.
          </p>
        </div>
      )}

      {/* Footer */}
      <div className={`flex items-center justify-end gap-2 px-5 py-3 ${styles.stepperFooter}`}>
        {step > 1 && (
          <button
            onClick={back}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${styles.btnBack}`}
          >
            이전
          </button>
        )}
        <button
          onClick={() => { setAgent(snapshot.current); navigate('/dashboard') }}
          className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${styles.btnCancel}`}
        >
          취소
        </button>
        {step < 5 ? (
          <button
            onClick={next}
            className={`rounded-lg px-4 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-85 ${styles.btnNext}`}
          >
            다음
          </button>
        ) : (
          <button
            onClick={save}
            disabled={loading}
            className={`rounded-lg px-4 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-85 ${styles.btnSave}`}
          >
            {loading ? '수집 중...' : '저장하기'}
          </button>
        )}
      </div>
    </div>
  )
}

function OptionGroup({ title, items, value, onSelect }) {
  return (
    <div>
      <p className={`mb-1.5 text-xs font-medium ${styles.stepMeta}`}>{title}</p>
      <div className="flex flex-wrap gap-1.5">
        {items.map(([itemValue, label]) => {
          const active = value === itemValue
          return (
            <button
              key={itemValue}
              onClick={() => onSelect(itemValue)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${active ? styles.filterBtnActive : styles.filterBtnInactive
                }`}
            >
              {label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
