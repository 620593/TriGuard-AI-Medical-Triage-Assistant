/**
 * VoiceInterface.jsx
 * ------------------
 * Full-screen voice interaction overlay for TriGuard AI.
 *
 * Props:
 *   onClose  : () => void         — exits voice mode, returns to chat
 *   onResult : (response) => void — adds voice result to chat history
 *   sessionId: string | null
 *   userId   : string | null
 *   token    : string | null
 */

import { useState, useRef, useEffect, useCallback } from "react";
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from "framer-motion";
import { Mic, X, RotateCcw, Volume2, AlertTriangle } from "lucide-react";
import CalmResultCard from "./CalmResultCard";

// ── Constants ────────────────────────────────────────────────────────────────
const API_BASE = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
const VOICE_URL = `${API_BASE}/api/v3/voice`;
const MAX_DURATION = 30_000; // 30-second auto-stop

// ── Helper: format mm:ss ─────────────────────────────────────────────────────
const fmtTime = (ms) => {
  const s = Math.floor(ms / 1000);
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
};

// ── PulseRing — animated ring around the mic ─────────────────────────────────
const PulseRing = ({ delay = 0, scale = 1 }) => (
  <motion.div
    className="absolute rounded-full border border-red-400/60"
    style={{ inset: `-${scale * 24}px` }}
    animate={{ scale: [1, 1.35, 1], opacity: [0.7, 0, 0.7] }}
    transition={{ duration: 1.6, delay, repeat: Infinity, ease: "easeInOut" }}
  />
);

// ── SoundWave — animated bars shown while playing audio ──────────────────────
const SoundWave = () => (
  <div className="flex items-end justify-center gap-[3px] h-8">
    {[0.6, 1, 0.7, 0.9, 0.5, 1, 0.8, 0.6, 0.9, 0.7].map((h, i) => (
      <motion.div
        key={i}
        className="w-[3px] rounded-full bg-teal-400"
        animate={{ scaleY: [h * 0.3, h, h * 0.3] }}
        transition={{
          duration: 0.7,
          delay: i * 0.07,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        style={{ height: "100%", originY: 1 }}
      />
    ))}
  </div>
);

// ── ThinkingDots ─────────────────────────────────────────────────────────────
const ThinkingDots = () => (
  <div className="flex gap-1.5 items-center">
    {[0, 1, 2].map((i) => (
      <motion.div
        key={i}
        className="w-2.5 h-2.5 rounded-full bg-teal-400"
        animate={{ y: [0, -10, 0] }}
        transition={{
          duration: 0.7,
          delay: i * 0.15,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
    ))}
  </div>
);

// ── Main component ────────────────────────────────────────────────────────────
const VoiceInterface = ({ onClose, onResult, sessionId, userId, token }) => {
  // voiceState: 'idle' | 'recording' | 'processing' | 'responding' | 'error'
  const [voiceState, setVoiceState] = useState("idle");
  const [transcript, setTranscript] = useState("");
  const [responseText, setResponseText] = useState("");
  const [riskLevel, setRiskLevel] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [elapsed, setElapsed] = useState(0); // recording ms counter
  const [audioFinished, setAudioFinished] = useState(false);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioRef = useRef(null); // <Audio> object for playback
  const timerRef = useRef(null); // setInterval for elapsed counter
  const autoStopRef = useRef(null); // setTimeout for 30-second auto-stop

  // ── Cleanup on unmount ───────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      clearInterval(timerRef.current);
      clearTimeout(autoStopRef.current);
      audioRef.current?.pause();
      mediaRecorderRef.current?.stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  // ── Start recording ──────────────────────────────────────────────────────
  const startRecording = useCallback(async () => {
    setErrorMsg("");
    setTranscript("");
    setResponseText("");
    setRiskLevel(null);
    setAudioFinished(false);
    setElapsed(0);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        clearInterval(timerRef.current);
        clearTimeout(autoStopRef.current);
        sendAudio();
      };

      recorder.start(250); // collect data every 250ms
      setVoiceState("recording");

      // Elapsed timer
      const startedAt = Date.now();
      timerRef.current = setInterval(
        () => setElapsed(Date.now() - startedAt),
        250,
      );

      // Auto-stop after MAX_DURATION
      autoStopRef.current = setTimeout(() => stopRecording(), MAX_DURATION);
    } catch (err) {
      setErrorMsg("Microphone access denied. Please allow mic permissions.");
      setVoiceState("error");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Stop recording ───────────────────────────────────────────────────────
  const stopRecording = useCallback(() => {
    clearInterval(timerRef.current);
    clearTimeout(autoStopRef.current);
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state !== "inactive"
    ) {
      mediaRecorderRef.current.stop();
    }
  }, []);

  // ── Send audio to backend ────────────────────────────────────────────────
  const sendAudio = useCallback(async () => {
    setVoiceState("processing");
    const blob = new Blob(audioChunksRef.current, { type: "audio/webm" });
    const file = new File([blob], "recording.webm", { type: "audio/webm" });

    const formData = new FormData();
    formData.append("audio", file);
    if (sessionId) formData.append("session_id", sessionId);
    if (userId) formData.append("user_id", userId);

    const headers = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    try {
      const res = await fetch(VOICE_URL, {
        method: "POST",
        body: formData,
        headers,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();

      setTranscript(data.transcription || "");
      setResponseText(data.response || "");
      setRiskLevel(data.risk_level || null);

      // Notify parent to add to chat history
      onResult?.({
        transcription: data.transcription,
        response: data.response,
        risk_level: data.risk_level,
        audio_url: data.audio_url || null,
        session_id: data.session_id,
      });

      setVoiceState("responding");

      // ── Audio playback ────────────────────────────────────────────────
      if (data.audio_url) {
        playAudio(data.audio_url);
      } else if (data.response) {
        // Fallback: browser speechSynthesis
        speakFallback(data.response);
      } else {
        setAudioFinished(true);
      }
    } catch (err) {
      setErrorMsg(err.message || "Something went wrong. Please try again.");
      setVoiceState("error");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, userId, token, onResult]);

  // ── Play returned .mp3 ───────────────────────────────────────────────────
  const playAudio = (url) => {
    const audio = new Audio(url);
    audioRef.current = audio;
    audio.onended = () => setAudioFinished(true);
    audio.onerror = () => {
      // If audio fetch fails, fall back to browser TTS
      speakFallback(responseText);
    };
    audio.play().catch(() => speakFallback(responseText));
  };

  // ── Browser speechSynthesis fallback ────────────────────────────────────
  const speakFallback = (text) => {
    if (!window.speechSynthesis || !text) {
      setAudioFinished(true);
      return;
    }
    window.speechSynthesis.cancel();
    const utt = new SpeechSynthesisUtterance(text.slice(0, 500));
    utt.lang = "en-US";
    utt.onend = () => setAudioFinished(true);
    window.speechSynthesis.speak(utt);
  };

  // ── Replay button ────────────────────────────────────────────────────────
  const replayAudio = () => {
    if (audioRef.current) {
      setAudioFinished(false);
      audioRef.current.currentTime = 0;
      audioRef.current.play().catch(() => {});
      audioRef.current.onended = () => setAudioFinished(true);
    }
  };

  // ── Mic button click: idle→record, record→stop ───────────────────────────
  const handleMicClick = () => {
    if (voiceState === "idle" || voiceState === "error") {
      startRecording();
    } else if (voiceState === "recording") {
      stopRecording();
    }
  };

  // ── Derived UI texts ─────────────────────────────────────────────────────
  const stateLabel =
    {
      idle: "Tap to speak",
      recording: "Listening…",
      processing: "Analyzing your symptoms…",
      responding: audioFinished ? "Done" : "Playing response…",
      error: "Something went wrong",
    }[voiceState] ?? "";

  const isRecording = voiceState === "recording";
  const isProcessing = voiceState === "processing";
  const isResponding = voiceState === "responding";
  const isError = voiceState === "error";
  const isIdle = voiceState === "idle";
  const showMicBtn = isIdle || isRecording || isError;

  return (
    <motion.div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      style={{
        background:
          "radial-gradient(ellipse at 50% 60%, rgba(255,255,255,0.98) 0%, rgba(241,245,249,1) 100%)",
      }}
    >
      {/* ── Close button ────────────────────────────────────────────────── */}
      <button
        onClick={onClose}
        className="absolute top-5 right-5 p-2 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 hover:text-slate-800 transition-all"
        aria-label="Close voice interface"
      >
        <X size={22} />
      </button>

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="absolute top-5 left-5">
        <p className="text-xs font-semibold tracking-widest uppercase text-teal-600">
          TriGuard Voice
        </p>
      </div>

      {/* ── Central Mic + rings ──────────────────────────────────────────── */}
      <div className="flex flex-col items-center gap-10">
        <div className="relative flex items-center justify-center">
          {/* Pulse rings while recording */}
          {isRecording && (
            <>
              <PulseRing delay={0} scale={1} />
              <PulseRing delay={0.5} scale={2} />
              <PulseRing delay={1} scale={3} />
            </>
          )}

          {/* Mic / State button */}
          <AnimatePresence mode="wait">
            {isProcessing ? (
              <motion.div
                key="processing"
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.8, opacity: 0 }}
                className="w-36 h-36 rounded-full bg-teal-500/10 border border-teal-500/30 flex items-center justify-center"
              >
                <ThinkingDots />
              </motion.div>
            ) : isResponding ? (
              <motion.div
                key="responding"
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.8, opacity: 0 }}
                className="w-36 h-36 rounded-full bg-teal-500/10 border border-teal-500/30 flex items-center justify-center"
              >
                {audioFinished ? (
                  <Volume2 size={44} className="text-teal-400" />
                ) : (
                  <SoundWave />
                )}
              </motion.div>
            ) : (
              <motion.button
                key="mic"
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.8, opacity: 0 }}
                onClick={handleMicClick}
                disabled={isProcessing}
                className={`relative w-36 h-36 rounded-full flex items-center justify-center transition-all duration-300 shadow-2xl focus:outline-none ${
                  isRecording
                    ? "bg-gradient-to-b from-red-500 to-red-700 shadow-red-500/40 ring-4 ring-red-400/30"
                    : isError
                      ? "bg-gradient-to-b from-orange-500 to-orange-700 shadow-orange-500/40"
                      : "bg-gradient-to-b from-teal-500 to-cyan-700 shadow-teal-500/40 hover:from-teal-400 hover:to-cyan-600 active:scale-95"
                }`}
                whileTap={{ scale: 0.93 }}
              >
                {isError ? (
                  <AlertTriangle size={44} className="text-white" />
                ) : (
                  <Mic size={44} className="text-white drop-shadow-lg" />
                )}
              </motion.button>
            )}
          </AnimatePresence>
        </div>

        {/* ── State label + timer ──────────────────────────────────────────── */}
        <div className="flex flex-col items-center gap-2 min-h-[3rem]">
          <motion.p
            key={stateLabel}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className={`text-lg font-semibold tracking-wide ${
              isError ? "text-orange-500" : "text-slate-800"
            }`}
          >
            {stateLabel}
          </motion.p>

          {isRecording && (
            <motion.span
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="font-mono text-sm text-red-600"
            >
              {fmtTime(elapsed)}
            </motion.span>
          )}

          {isError && errorMsg && (
            <p className="text-xs text-orange-500 max-w-xs text-center mt-1">
              {errorMsg}
            </p>
          )}
        </div>

        {/* ── Transcript output ────────────────────────────────────────────── */}
        <AnimatePresence>
          {transcript && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              className="max-w-sm w-full mx-4 px-5 py-3 rounded-2xl bg-white border border-slate-200 shadow-sm"
            >
              <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-1">
                You said
              </p>
              <p className="text-sm text-slate-800 leading-relaxed">
                🎙️ {transcript}
              </p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── AI response text ─────────────────────────────────────────────── */}
        <AnimatePresence>
          {responseText && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              className="max-w-xl w-full mx-4"
            >
              <CalmResultCard
                riskLevel={riskLevel || "low"}
                title="Here's what we found"
                subtitle="Voice screening • Always verify with a doctor"
              >
                <p className="text-base leading-relaxed text-slate-700 line-clamp-6">
                  {responseText}
                </p>
              </CalmResultCard>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Action buttons ───────────────────────────────────────────────── */}
        <div className="flex gap-3">
          {/* Replay button — shows after audio finishes */}
          {isResponding && audioFinished && audioRef.current && (
            <motion.button
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              onClick={replayAudio}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-slate-600 hover:text-slate-900 text-sm transition-all shadow-sm"
            >
              <RotateCcw size={14} />
              Replay
            </motion.button>
          )}

          {/* Ask another — shown after response is done */}
          {(isResponding && audioFinished) || isError ? (
              <motion.button
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              onClick={() => {
                window.speechSynthesis?.cancel();
                audioRef.current?.pause();
                setVoiceState("idle");
                setTranscript("");
                setResponseText("");
                setRiskLevel(null);
                setErrorMsg("");
                setAudioFinished(false);
                setElapsed(0);
              }}
              className="flex items-center gap-2 px-5 py-2 rounded-xl bg-teal-50 hover:bg-teal-100 border border-teal-200 text-teal-700 hover:text-teal-900 text-sm font-semibold transition-all shadow-sm"
            >
              <Mic size={14} />
              Ask another
            </motion.button>
          ) : null}
        </div>
      </div>

      {/* ── Bottom hint ─────────────────────────────────────────────────────── */}
      {(isIdle || isRecording) && (
        <motion.p
          className="absolute bottom-8 text-xs text-slate-500 tracking-wide"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          {isIdle
            ? "Tap the mic to start recording"
            : "Tap the mic again to stop"}
        </motion.p>
      )}
    </motion.div>
  );
};

export default VoiceInterface;
