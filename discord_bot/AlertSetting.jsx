import { useEffect, useState } from "react";

const KEYWORDS = ["AI", "NLP", "CV", "Robotics", "ML", "LLM"];
const BOT_INVITE_URL = "https://discord.com/oauth2/authorize?client_id=1490910406485475449&permissions=85056&integration_type=0&scope=bot";
const API_BASE_URL = (() => {
  if (typeof window === "undefined") {
    return "http://127.0.0.1:8000";
  }

  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get("api");
  if (fromQuery) {
    window.localStorage.setItem("alert_api_base_url", fromQuery);
    return fromQuery;
  }

  return window.localStorage.getItem("alert_api_base_url") || "http://127.0.0.1:8000";
})();

export default function AlertSetting() {
  const [step, setStep] = useState("select"); // select -> login -> install -> channel -> done
  const [selectedKeywords, setSelectedKeywords] = useState([]);
  const [includeSummary, setIncludeSummary] = useState(false);
  const [includeCategory, setIncludeCategory] = useState(false);
  const [alertMode, setAlertMode] = useState("daily");
  const [dailyTime, setDailyTime] = useState("09:00");
  const [saving, setSaving] = useState(false);
  const [loadingChannels, setLoadingChannels] = useState(false);
  const [channels, setChannels] = useState([]);
  const [selectedChannelKey, setSelectedChannelKey] = useState("");
  const [alertId, setAlertId] = useState("");
  const [autoAlerts, setAutoAlerts] = useState([]);
  const [loadingAutoAlerts, setLoadingAutoAlerts] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [oauthSessionId, setOauthSessionId] = useState("");
  const [oauthUser, setOauthUser] = useState(null);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const params = new URLSearchParams(window.location.search);
    const fromQuery = params.get("auth_session");
    const fromStorage = window.localStorage.getItem("discord_auth_session") || "";
    const sessionId = fromQuery || fromStorage;
    if (!sessionId) {
      return;
    }

    if (fromQuery) {
      window.localStorage.setItem("discord_auth_session", fromQuery);
      params.delete("auth_session");
      const nextQuery = params.toString();
      const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}`;
      window.history.replaceState({}, "", nextUrl);
    }

    setOauthSessionId(sessionId);
    fetch(`${API_BASE_URL}/api/auth/session/${sessionId}`)
      .then((res) => {
        if (!res.ok) {
          throw new Error("로그인 세션 조회 실패");
        }
        return res.json();
      })
      .then((data) => {
        setOauthUser(data?.user || null);
      })
      .catch(() => {
        setOauthSessionId("");
        setOauthUser(null);
        window.localStorage.removeItem("discord_auth_session");
      });
  }, []);

  const toggleKeyword = (keyword) => {
    setSelectedKeywords((prev) =>
      prev.includes(keyword)
        ? prev.filter((k) => k !== keyword)
        : [...prev, keyword]
    );
  };

  const savePreferences = async () => {
    if (selectedKeywords.length === 0) {
      setErrorMessage("키워드를 1개 이상 선택해 주세요.");
      return false;
    }

    setSaving(true);
    setErrorMessage("");
    try {
      const response = await fetch(`${API_BASE_URL}/api/alert-preferences`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          keywords: selectedKeywords,
          include_summary: includeSummary,
          include_category: includeCategory,
          alert_mode: alertMode,
          daily_time: dailyTime,
          discord_user_id: oauthUser?.id || null,
        }),
      });

      if (!response.ok) {
        throw new Error(`설정 저장 실패 (${response.status})`);
      }
      const data = await response.json();
      const savedAlertId = data?.alert_id || "";
      if (savedAlertId) {
        setAlertId(savedAlertId);
      }
      return savedAlertId;
    } catch (error) {
      setErrorMessage(error?.message || "설정 저장 중 오류가 발생했습니다.");
      return "";
    } finally {
      setSaving(false);
    }
  };

  const handleDiscordLogin = async () => {
    setSaving(true);
    setErrorMessage("");
    try {
      const redirectBack = `${window.location.origin}${window.location.pathname}?api=${encodeURIComponent(API_BASE_URL)}`;
      const response = await fetch(`${API_BASE_URL}/api/auth/discord/login-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ redirect_back: redirectBack }),
      });
      if (!response.ok) {
        throw new Error(`로그인 URL 생성 실패 (${response.status})`);
      }
      const data = await response.json();
      if (!data?.url) {
        throw new Error("로그인 URL이 비어 있습니다.");
      }
      window.location.href = data.url;
    } catch (error) {
      setErrorMessage(error?.message || "디스코드 로그인 시작 실패");
    } finally {
      setSaving(false);
    }
  };

  const handleBotInstall = async () => {
    const savedAlertId = await savePreferences();
    if (!savedAlertId) {
      return;
    }
    window.open(BOT_INVITE_URL, "_blank");
    setStep("done");
  };

  const handleAlreadyInstalled = async () => {
    const savedAlertId = await savePreferences();
    if (!savedAlertId) {
      return;
    }

    setLoadingChannels(true);
    setErrorMessage("");
    try {
      if (!oauthSessionId) {
        throw new Error("디스코드 로그인이 필요합니다.");
      }
      const response = await fetch(`${API_BASE_URL}/api/bot/channels?session_id=${encodeURIComponent(oauthSessionId)}`);
      if (!response.ok) {
        throw new Error(`채널 목록 조회 실패 (${response.status})`);
      }
      const data = await response.json();
      const rows = data?.channels || [];
      setChannels(rows);
      if (rows.length > 0) {
        setSelectedChannelKey(`${rows[0].guild_id}:${rows[0].channel_id}`);
      }
      setStep("channel");
    } catch (error) {
      setErrorMessage(error?.message || "채널 목록을 가져오지 못했습니다.");
    } finally {
      setLoadingChannels(false);
    }
  };

  const handleBindSelectedChannel = async () => {
    if (!alertId) {
      setErrorMessage("알림 설정 ID가 없어 채널을 저장할 수 없습니다.");
      return;
    }
    if (!selectedChannelKey) {
      setErrorMessage("채널을 선택해 주세요.");
      return;
    }

    const [guildIdText, channelIdText] = selectedChannelKey.split(":");
    const guildId = guildIdText;
    const channelId = channelIdText;

    setSaving(true);
    setErrorMessage("");
    try {
      const response = await fetch(`${API_BASE_URL}/api/alerts/bind-channel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          alert_id: alertId,
          guild_id: guildId,
          channel_id: channelId,
        }),
      });
      if (!response.ok) {
        throw new Error(`채널 저장 실패 (${response.status})`);
      }
      setStep("done");
    } catch (error) {
      setErrorMessage(error?.message || "채널 저장 중 오류가 발생했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const fetchAutoAlerts = async () => {
    setLoadingAutoAlerts(true);
    setErrorMessage("");
    try {
      const response = await fetch(`${API_BASE_URL}/api/auto-alerts`);
      if (!response.ok) {
        throw new Error(`자동알림 조회 실패 (${response.status})`);
      }
      const data = await response.json();
      setAutoAlerts(data?.alerts || []);
    } catch (error) {
      setErrorMessage(error?.message || "자동알림 목록 조회 실패");
    } finally {
      setLoadingAutoAlerts(false);
    }
  };

  const deleteAutoAlert = async (targetAlertId) => {
    setSaving(true);
    setErrorMessage("");
    try {
      const response = await fetch(`${API_BASE_URL}/api/auto-alerts/${targetAlertId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(`자동알림 삭제 실패 (${response.status})`);
      }
      await fetchAutoAlerts();
    } catch (error) {
      setErrorMessage(error?.message || "자동알림 삭제 실패");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh",
      background: "#0f0f13",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontFamily: "'DM Sans', sans-serif",
      padding: "24px"
    }}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet" />

      <div style={{
        width: "100%",
        maxWidth: 480,
        background: "#18181f",
        borderRadius: 20,
        border: "1px solid #2a2a35",
        padding: "36px 32px",
      }}>

        {/* 헤더 */}
        <div style={{ marginBottom: 32 }}>
          <div style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            background: "#5865F220",
            border: "1px solid #5865F240",
            borderRadius: 8,
            padding: "4px 12px",
            marginBottom: 16
          }}>
            <span style={{ fontSize: 13, color: "#7289da" }}>Discord 알림 설정</span>
          </div>
          <h1 style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 26,
            fontWeight: 700,
            color: "#f0f0f5",
            margin: 0,
            lineHeight: 1.3
          }}>
            {step === "select" && "어떤 논문 알림을 받을까요?"}
            {step === "login" && "디스코드 로그인"}
            {step === "install" && "봇 설치 진행"}
            {step === "channel" && "알림 채널 선택"}
            {step === "done" && "알림 설정 완료!"}
          </h1>
        </div>

        {/* 1단계: 키워드 + 옵션 선택 */}
        {step === "select" && (
          <>
            <p style={{ fontSize: 14, color: "#8888a0", marginBottom: 20, marginTop: 0 }}>
              관심 있는 분야를 선택하세요. 여러 개 선택 가능해요.
            </p>

            {/* 키워드 선택 */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 28 }}>
              {KEYWORDS.map((k) => (
                <button
                  key={k}
                  onClick={() => toggleKeyword(k)}
                  style={{
                    padding: "8px 18px",
                    borderRadius: 99,
                    border: selectedKeywords.includes(k)
                      ? "1.5px solid #5865F2"
                      : "1px solid #2a2a35",
                    background: selectedKeywords.includes(k) ? "#5865F220" : "transparent",
                    color: selectedKeywords.includes(k) ? "#7289da" : "#8888a0",
                    fontSize: 14,
                    fontFamily: "'DM Sans', sans-serif",
                    cursor: "pointer",
                    transition: "all 0.15s"
                  }}
                >
                  {k}
                </button>
              ))}
            </div>

            {/* 알림 메시지 옵션 */}
            <div style={{
              background: "#111117",
              border: "1px solid #2a2a35",
              borderRadius: 12,
              padding: "16px 20px",
              marginBottom: 28
            }}>
              <p style={{ fontSize: 13, color: "#8888a0", margin: "0 0 14px" }}>
                알림 메시지에 추가로 포함할 내용
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
                  <div
                    onClick={() => setIncludeSummary(!includeSummary)}
                    style={{
                      width: 18, height: 18,
                      borderRadius: 5,
                      border: includeSummary ? "none" : "1.5px solid #3a3a4a",
                      background: includeSummary ? "#5865F2" : "transparent",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      flexShrink: 0, cursor: "pointer"
                    }}
                  >
                    {includeSummary && (
                      <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                        <path d="M1 4L3.5 6.5L9 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                  </div>
                  <span style={{ fontSize: 14, color: "#c0c0d0" }}>요약 포함</span>
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
                  <div
                    onClick={() => setIncludeCategory(!includeCategory)}
                    style={{
                      width: 18, height: 18,
                      borderRadius: 5,
                      border: includeCategory ? "none" : "1.5px solid #3a3a4a",
                      background: includeCategory ? "#5865F2" : "transparent",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      flexShrink: 0, cursor: "pointer"
                    }}
                  >
                    {includeCategory && (
                      <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                        <path d="M1 4L3.5 6.5L9 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                  </div>
                  <span style={{ fontSize: 14, color: "#c0c0d0" }}>카테고리 포함</span>
                </label>
              </div>
              <p style={{ fontSize: 12, color: "#55556a", marginTop: 14, marginBottom: 0 }}>
                제목, 링크는 항상 포함돼요
              </p>
            </div>

            <div style={{
              background: "#111117",
              border: "1px solid #2a2a35",
              borderRadius: 12,
              padding: "16px 20px",
              marginBottom: 28
            }}>
              <p style={{ fontSize: 13, color: "#8888a0", margin: "0 0 14px" }}>
                알림 전송 방식
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 8, color: "#c0c0d0", fontSize: 14 }}>
                  <input
                    type="radio"
                    name="alertMode"
                    value="daily"
                    checked={alertMode === "daily"}
                    onChange={() => setAlertMode("daily")}
                  />
                  매일 지정 시각에 받기
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 8, color: "#c0c0d0", fontSize: 14 }}>
                  <input
                    type="radio"
                    name="alertMode"
                    value="once_now"
                    checked={alertMode === "once_now"}
                    onChange={() => setAlertMode("once_now")}
                  />
                  지금 1회만 받기
                </label>
              </div>

              {alertMode === "daily" && (
                <div style={{ marginTop: 14 }}>
                  <p style={{ fontSize: 12, color: "#55556a", margin: "0 0 8px" }}>알림 시간</p>
                  <input
                    type="time"
                    value={dailyTime}
                    onChange={(event) => setDailyTime(event.target.value)}
                    style={{
                      width: "100%",
                      boxSizing: "border-box",
                      padding: "10px 12px",
                      borderRadius: 8,
                      border: "1px solid #2a2a35",
                      background: "#0f0f13",
                      color: "#f0f0f5",
                    }}
                  />
                </div>
              )}
            </div>

            <button
              onClick={() => setStep("login")}
              disabled={selectedKeywords.length === 0}
              style={{
                width: "100%",
                padding: "14px",
                borderRadius: 12,
                border: "none",
                background: selectedKeywords.length > 0 ? "#5865F2" : "#2a2a35",
                color: selectedKeywords.length > 0 ? "white" : "#55556a",
                fontSize: 15,
                fontFamily: "'DM Sans', sans-serif",
                fontWeight: 600,
                cursor: selectedKeywords.length > 0 ? "pointer" : "not-allowed",
                transition: "all 0.15s"
              }}
            >
              다음 →
            </button>
          </>
        )}

        {/* 2단계: 디스코드 로그인 */}
        {step === "login" && (
          <>
            <p style={{ fontSize: 14, color: "#8888a0", marginBottom: 20, marginTop: 0 }}>
              디스코드 OAuth 로그인이 필요합니다. 로그인한 사용자 기준으로 서버/채널 목록을 제한합니다.
            </p>

            {oauthUser && (
              <p style={{ fontSize: 12, color: "#95f0a0", marginTop: 0, marginBottom: 10 }}>
                로그인됨: {oauthUser.global_name || oauthUser.username} ({oauthUser.id})
              </p>
            )}

            {errorMessage && (
              <p style={{ color: "#ff8f8f", fontSize: 12, marginTop: 0, marginBottom: 16 }}>
                {errorMessage}
              </p>
            )}

            <button
              onClick={handleDiscordLogin}
              disabled={saving}
              style={{
                width: "100%",
                padding: "14px",
                borderRadius: 12,
                border: "none",
                background: "#5865F2",
                color: "white",
                fontSize: 15,
                fontFamily: "'DM Sans', sans-serif",
                fontWeight: 600,
                cursor: "pointer",
                marginBottom: 12,
              }}
            >
              {saving ? "로그인 연결 중..." : oauthUser ? "다시 로그인" : "디스코드 로그인"}
            </button>

            <button
              onClick={() => setStep("install")}
              disabled={!oauthUser}
              style={{
                width: "100%",
                padding: "12px",
                borderRadius: 12,
                border: "1px solid #2a2a35",
                background: "transparent",
                color: oauthUser ? "#c0c0d0" : "#55556a",
                fontSize: 14,
                fontFamily: "'DM Sans', sans-serif",
                cursor: oauthUser ? "pointer" : "not-allowed",
                marginBottom: 10,
              }}
            >
              로그인 완료, 다음 단계로
            </button>

            <button
              onClick={() => setStep("select")}
              style={{
                width: "100%",
                padding: "12px",
                borderRadius: 12,
                border: "1px solid #2a2a35",
                background: "transparent",
                color: "#8888a0",
                fontSize: 14,
                fontFamily: "'DM Sans', sans-serif",
                cursor: "pointer",
              }}
            >
              ← 돌아가기
            </button>
          </>
        )}

        {/* 3단계: 봇 설치 */}
        {step === "install" && (
          <>
            <p style={{ fontSize: 14, color: "#8888a0", marginBottom: 28, marginTop: 0 }}>
              디스코드 봇으로 알림을 받으려면 봇 설치가 필요합니다. 아래 버튼으로 설치 페이지로 이동하세요.
            </p>

            {errorMessage && (
              <p style={{ color: "#ff8f8f", fontSize: 12, marginTop: 0, marginBottom: 16 }}>
                {errorMessage}
              </p>
            )}

            {/* 선택 요약 */}
            <div style={{
              background: "#111117",
              border: "1px solid #2a2a35",
              borderRadius: 12,
              padding: "14px 18px",
              marginBottom: 24
            }}>
              <p style={{ fontSize: 12, color: "#55556a", margin: "0 0 10px" }}>선택한 키워드</p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {selectedKeywords.map(k => (
                  <span key={k} style={{
                    background: "#5865F220",
                    color: "#7289da",
                    fontSize: 12,
                    padding: "3px 10px",
                    borderRadius: 99,
                    border: "1px solid #5865F230"
                  }}>{k}</span>
                ))}
              </div>
              <div style={{ display: "flex", gap: 12, marginTop: 10 }}>
                {includeSummary && <span style={{ fontSize: 12, color: "#55556a" }}>+ 요약</span>}
                {includeCategory && <span style={{ fontSize: 12, color: "#55556a" }}>+ 카테고리</span>}
                {alertMode === "daily" && <span style={{ fontSize: 12, color: "#55556a" }}>+ 매일 {dailyTime}</span>}
                {alertMode === "once_now" && <span style={{ fontSize: 12, color: "#55556a" }}>+ 지금 1회</span>}
              </div>
            </div>

            <button
              onClick={handleBotInstall}
              disabled={saving}
              style={{
                width: "100%",
                padding: "14px",
                borderRadius: 12,
                border: "none",
                background: saving ? "#2a2a35" : "#5865F2",
                color: "white",
                fontSize: 15,
                fontFamily: "'DM Sans', sans-serif",
                fontWeight: 600,
                cursor: saving ? "not-allowed" : "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 10,
                marginBottom: 12
              }}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="white">
                <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03z" />
              </svg>
              {saving ? "저장 중..." : "설정 저장 후 디스코드로 봇 추가하기"}
            </button>

            <button
              onClick={handleAlreadyInstalled}
              disabled={saving || loadingChannels}
              style={{
                width: "100%",
                padding: "12px",
                borderRadius: 12,
                border: "1px solid #2a2a35",
                background: "transparent",
                color: "#c0c0d0",
                fontSize: 14,
                fontFamily: "'DM Sans', sans-serif",
                cursor: saving || loadingChannels ? "not-allowed" : "pointer",
                marginBottom: 12,
              }}
            >
              {loadingChannels ? "채널 불러오는 중..." : "이미 봇 설치되어 있습니다"}
            </button>

            <button
              onClick={() => setStep("login")}
              style={{
                width: "100%",
                padding: "12px",
                borderRadius: 12,
                border: "1px solid #2a2a35",
                background: "transparent",
                color: "#8888a0",
                fontSize: 14,
                fontFamily: "'DM Sans', sans-serif",
                cursor: "pointer"
              }}
            >
              ← 이전 단계
            </button>
          </>
        )}

        {step === "channel" && (
          <>
            <p style={{ fontSize: 14, color: "#8888a0", marginBottom: 16, marginTop: 0 }}>
              설치된 봇이 접근 가능한 채널입니다. 알림을 보낼 채널을 선택하세요.
            </p>

            {channels.length === 0 ? (
              <p style={{ fontSize: 13, color: "#ff8f8f", marginBottom: 16 }}>
                불러온 채널이 없습니다. 봇이 서버에 설치되었는지 확인해 주세요.
              </p>
            ) : (
              <select
                value={selectedChannelKey}
                onChange={(event) => setSelectedChannelKey(event.target.value)}
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  padding: "12px",
                  borderRadius: 10,
                  border: "1px solid #2a2a35",
                  background: "#111117",
                  color: "#f0f0f5",
                  marginBottom: 16,
                }}
              >
                {channels.map((row) => (
                  <option key={`${row.guild_id}:${row.channel_id}`} value={`${row.guild_id}:${row.channel_id}`}>
                    {row.guild_name} / #{row.channel_name}
                  </option>
                ))}
              </select>
            )}

            {errorMessage && (
              <p style={{ color: "#ff8f8f", fontSize: 12, marginTop: 0, marginBottom: 16 }}>
                {errorMessage}
              </p>
            )}

            <button
              onClick={handleBindSelectedChannel}
              disabled={saving || channels.length === 0}
              style={{
                width: "100%",
                padding: "12px",
                borderRadius: 12,
                border: "none",
                background: saving || channels.length === 0 ? "#2a2a35" : "#5865F2",
                color: "#fff",
                cursor: saving || channels.length === 0 ? "not-allowed" : "pointer",
                marginBottom: 12,
              }}
            >
              {saving ? "저장 중..." : "선택 채널로 알림 저장"}
            </button>

            <button
              onClick={() => setStep("install")}
              style={{
                width: "100%",
                padding: "12px",
                borderRadius: 12,
                border: "1px solid #2a2a35",
                background: "transparent",
                color: "#8888a0",
                fontSize: 14,
                fontFamily: "'DM Sans', sans-serif",
                cursor: "pointer"
              }}
            >
              ← 이전 단계
            </button>
          </>
        )}

        {/* 4단계: 완료 */}
        {step === "done" && (
          <div style={{ textAlign: "center" }}>
            <div style={{
              width: 64, height: 64,
              background: "#5865F220",
              borderRadius: 99,
              display: "flex", alignItems: "center", justifyContent: "center",
              margin: "0 auto 20px"
            }}>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
                <path d="M5 13l4 4L19 7" stroke="#7289da" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <p style={{ fontSize: 15, color: "#8888a0", marginBottom: 28, marginTop: 0, lineHeight: 1.7 }}>
              알림 설정 완료되었습니다.<br />
              {alertMode === "daily" ? `매일 ${dailyTime}에 자동 전송됩니다.` : "지금 1회 전송이 설정되었습니다."}
            </p>
            <div style={{
              background: "#111117",
              border: "1px solid #2a2a35",
              borderRadius: 12,
              padding: "14px 18px",
              textAlign: "left",
              marginBottom: 24
            }}>
              <p style={{ fontSize: 12, color: "#55556a", margin: "0 0 8px" }}>알림 메시지 예시</p>
              <p style={{ fontSize: 13, color: "#c0c0d0", margin: 0, lineHeight: 1.7 }}>
                📄 <strong>Attention Is All You Need</strong><br />
                🔗 https://arxiv.org/abs/1706.03762
                {includeCategory && <><br />🏷️ AI</>}
                {includeSummary && <><br />📝 트랜스포머 구조를 제안한 논문입니다.</>}
              </p>
            </div>

            {errorMessage && (
              <p style={{ color: "#ff8f8f", fontSize: 12, marginTop: 0, marginBottom: 12 }}>
                {errorMessage}
              </p>
            )}

            <button
              onClick={fetchAutoAlerts}
              disabled={loadingAutoAlerts}
              style={{
                width: "100%",
                padding: "10px",
                borderRadius: 10,
                border: "1px solid #2a2a35",
                background: "transparent",
                color: "#ddd",
                marginBottom: 12,
                cursor: loadingAutoAlerts ? "not-allowed" : "pointer",
              }}
            >
              {loadingAutoAlerts ? "불러오는 중..." : "저장된 자동알림 목록 보기"}
            </button>

            {autoAlerts.length > 0 && (
              <div style={{ marginBottom: 12, textAlign: "left" }}>
                <p style={{ fontSize: 12, color: "#8888a0", margin: "0 0 8px" }}>
                  총 {autoAlerts.length}개 저장됨
                </p>
                <div
                  style={{
                    maxHeight: 240,
                    overflowY: "auto",
                    paddingRight: 4,
                  }}
                >
                  {autoAlerts.map((row) => (
                    <div
                      key={row.alert_id}
                      style={{
                        border: "1px solid #2a2a35",
                        borderRadius: 10,
                        padding: "10px 12px",
                        marginBottom: 8,
                        background: "#111117",
                        textAlign: "left",
                      }}
                    >
                      <div style={{ fontSize: 12, color: "#c0c0d0", marginBottom: 4 }}>
                        ID: {row.alert_id}
                      </div>
                      <div style={{ fontSize: 12, color: "#8888a0", marginBottom: 8 }}>
                        mode: {row.alert_mode} / time: {row.daily_time} / status: {row.status}
                      </div>
                      <button
                        onClick={() => deleteAutoAlert(row.alert_id)}
                        disabled={saving}
                        style={{
                          padding: "6px 10px",
                          borderRadius: 8,
                          border: "1px solid #3a2a2a",
                          background: "#2a1515",
                          color: "#ffb3b3",
                          fontSize: 12,
                          cursor: saving ? "not-allowed" : "pointer",
                        }}
                      >
                        이 알림 삭제
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <button
              onClick={() => {
                setStep("select");
                setSelectedKeywords([]);
                setIncludeSummary(false);
                setIncludeCategory(false);
                setAlertMode("daily");
                setDailyTime("09:00");
                setChannels([]);
                setSelectedChannelKey("");
                setAlertId("");
                setAutoAlerts([]);
                setErrorMessage("");
              }}
              style={{
                width: "100%",
                padding: "12px",
                borderRadius: 12,
                border: "1px solid #2a2a35",
                background: "transparent",
                color: "#8888a0",
                fontSize: 14,
                fontFamily: "'DM Sans', sans-serif",
                cursor: "pointer"
              }}
            >
              처음으로
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
