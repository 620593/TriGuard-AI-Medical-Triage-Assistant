import { useState, useRef, useEffect, useCallback } from "react";
import DOMPurify from "dompurify";
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from "framer-motion";
import {
  Send,
  Paperclip,
  Camera,
  Globe,
  Loader2,
  Bot,
  User,
  Activity,
  FileText,
  Stethoscope,
  X,
  Image,
  ScanSearch,
  FileScan,
  RefreshCw,
} from "lucide-react";
import { triageAPI } from "../api/client";
import RiskBadge from "../components/RiskBadge";
import VoiceToggle from "../components/VoiceToggle";
import VoiceInterface from "../components/VoiceInterface";
import TriageResponseCard from "../components/TriageResponseCard";
import XrayResultCard from "../components/XrayResultCard";

/** Sanitize once at creation time and convert newlines to <br/> */
const sanitize = (text) =>
  DOMPurify.sanitize((text ?? "").replace(/\n/g, "<br/>"));

const TriageChat = () => {
  const [messages, setMessages] = useState([
    {
      id: "initial-welcome",
      role: "assistant",
      content:
        "Hello! I am TriGuard AI. How are you feeling today? You can describe your symptoms, upload a document, or use voice mode.",
      html: sanitize(
        "Hello! I am TriGuard AI. How are you feeling today? You can describe your symptoms, upload a document, or use voice mode.",
      ),
      type: "text",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isVoiceActive, setIsVoiceActive] = useState(false);
  const [voiceMode, setVoiceMode] = useState(false); // true = fullscreen VoiceInterface
  const [sessionID, setSessionID] = useState(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [consentForCall, setConsentForCall] = useState(false); // emergency call consent
  // imageTypeModal holds the pending File waiting for the user to select its type
  const [imageTypeModal, setImageTypeModal] = useState(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const chatEndRef = useRef(null);

  // ── Voice mode helpers ─────────────────────────────────────────────────────
  /** Open fullscreen voice interface */
  const openVoiceMode = () => {
    // Stop any in-progress inline recording before switching modes
    if (isVoiceActive) stopRecording();
    setVoiceMode(true);
  };

  /** Called when VoiceInterface returns a result — merge into chat history */
  const handleVoiceResult = (result) => {
    if (result.session_id) setSessionID(result.session_id);
    setMessages((prev) =>
      [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "user",
          content: `🎙️ ${result.transcription}`,
          html: sanitize(`🎙️ ${result.transcription}`),
          type: "voice_input",
        },
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: result.response,
          html: sanitize(result.response),
          risk: result.risk_level,
          type: "voice",
          // data.audio_url is already the full URL from backend — use directly
          audioUrl: result.audio_url || null,
        },
      ].slice(-50),
    );
  };

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // Voice Recording Logic
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, {
          type: "audio/webm",
        });
        const file = new File([audioBlob], "recording.webm", {
          type: "audio/webm",
        });
        await handleVoiceUpload(file);
        stream.getTracks().forEach((track) => track.stop());
      };

      recorder.start();
      setIsVoiceActive(true);
    } catch (err) {
      console.error("Recording Error:", err);
      // Voice Error UI Instead of alert
      setMessages((prev) =>
        [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content:
              "I couldn't access your microphone. Please check your browser permissions.",
            html: sanitize(
              "I couldn't access your microphone. Please check your browser permissions.",
            ),
            type: "text",
            error: true,
          },
        ].slice(-50),
      );
    }
  };

  const stopRecording = () => {
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state !== "inactive"
    ) {
      mediaRecorderRef.current.stop();
      setIsVoiceActive(false);
    }
  };

  const handleVoiceUpload = async (file) => {
    const formData = new FormData();
    formData.append("audio", file);
    if (sessionID) formData.append("session_id", sessionID);

    setIsLoading(true);
    try {
      const response = await triageAPI.voice(formData);
      const data = response?.data;
      if (!data) throw new Error("Empty response");

      if (data.session_id) setSessionID(data.session_id);

      setMessages((prev) => {
        const newHistory = [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "user",
            content: `🎙️ ${data.transcription}`,
            html: sanitize(`🎙️ ${data.transcription}`),
            type: "voice_input",
          },
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: data.response,
            html: sanitize(data.response),
            risk: data.risk_level,
            type: "voice",
            // data.audio_url is already a full URL (e.g. http://localhost:8000/static/audio/triage_abc.mp3)
            // Do NOT pass it through getStaticAudioUrl() — that would double-wrap the path.
            audioUrl: data.audio_url || null,
          },
        ];
        return newHistory.slice(-50); // Keep max 50 trailing messages in memory
      });
    } catch (error) {
      console.error("Voice Error:", error);
      setMessages((prev) =>
        [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: "Sorry, I had trouble processing your voice.",
            html: sanitize("Sorry, I had trouble processing your voice."),
            type: "text",
            error: true,
          },
        ].slice(-50),
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: input,
      html: sanitize(input),
      type: "text",
    };
    setMessages((prev) => [...prev, userMessage].slice(-50));
    setInput("");
    setIsLoading(true);

    try {
      const response = await triageAPI.triage({
        // Always include session_id (null on first message starts a new session)
        session_id: sessionID,
        message: input,
        user_consent_for_call: consentForCall,
      });

      const data = response?.data;
      if (!data) throw new Error("Empty response");

      // Store session_id from first response — send it on every subsequent turn
      if (data.session_id) setSessionID(data.session_id);

      // Build the nutrition image URL from filename (if HF generated one)
      const nutritionImgUrl = triageAPI.getStaticNutritionUrl(
        data.nutrition_image,
      );

      const aiMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: data.response,
        html: sanitize(data.response),
        risk: data.risk_level,
        parsed: data.parsed_response || null, // structured sections for rich card
        nutritionImageUrl: nutritionImgUrl, // HuggingFace-generated meal image
        type: "text",
      };

      setMessages((prev) => [...prev, aiMessage].slice(-50));
    } catch (error) {
      console.error("Triage Error:", error);
      setMessages((prev) =>
        [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content:
              "I encountered an error connecting to the medical server. Please try again.",
            html: sanitize(
              "I encountered an error connecting to the medical server. Please try again.",
            ),
            error: true,
          },
        ].slice(-50),
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (event, type) => {
    const file = event.target.files[0];
    if (!file || isLoading) return;

    const formData = new FormData();
    formData.append("image", file);
    if (sessionID) formData.append("session_id", sessionID);

    // Determine display label and correct API route
    const typeLabels = {
      document: "Medical Document",
      image: "Body Image",
      xray: "X-Ray Image",
    };

    setMessages((prev) =>
      [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "user",
          content: `📎 Uploaded ${typeLabels[type] || type}: ${file.name}`,
          html: sanitize(
            `📎 Uploaded ${typeLabels[type] || type}: ${file.name}`,
          ),
          type: "file",
        },
      ].slice(-50),
    );
    setIsLoading(true);

    try {
      let response;
      if (type === "xray") {
        // X-ray always goes to /xray endpoint — always routes xray analysis node
        response = await triageAPI.xray(formData);
      } else {
        // Both 'document' and 'image' use /image endpoint,
        // but pass an image_type_hint so the classification node routes correctly:
        //   document → OCR scan → symptom extraction (medical report pipeline)
        //   image    → medical vision pipeline
        const hint = type === "document" ? "report" : "body";
        formData.append("image_type_hint", hint);
        response = await triageAPI.image(formData);
      }

      const data = response?.data;
      if (!data) throw new Error("Empty response");

      if (data.session_id) setSessionID(data.session_id);

      let content = data.summary || data.analysis || data.response;
      if (data.nutrition_advice) {
        content += `\n\n### 🍎 Dietary Advice\n${data.nutrition_advice}`;
      }

      setMessages((prev) =>
        [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: content,
            html: sanitize(content),
            risk: data.risk_level,
            type: type === "xray" ? "xray" : "text",
            imageUrl: triageAPI.getStaticNutritionUrl(
              data.nutrition_image || data.image_url,
            ),
          },
        ].slice(-50),
      );
    } catch (error) {
      console.error("Upload Error:", error);
      setMessages((prev) =>
        [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content:
              "Sorry, I had an error processing this file. Please ensure it is a valid image or PDF.",
            html: sanitize(
              "Sorry, I had an error processing this file. Please ensure it is a valid image or PDF.",
            ),
            type: "text",
            error: true,
          },
        ].slice(-50),
      );
    } finally {
      setIsLoading(false);
      event.target.value = null;
    }
  };

  // ── Shared handler for files arriving from paste / drag-drop ──────────────
  const ACCEPTED_MIME = [
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/tiff",
    "application/pdf",
  ];

  const handleImageFile = (file) => {
    if (!file) return;
    if (!ACCEPTED_MIME.includes(file.type) && !file.type.startsWith("image/")) {
      setMessages((prev) =>
        [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: `Unsupported file type: ${file.type || "unknown"}. Please upload an image (JPEG, PNG, WebP, GIF, BMP, TIFF) or PDF.`,
            html: sanitize(`Unsupported file type: ${file.type || "unknown"}.`),
            type: "text",
            error: true,
          },
        ].slice(-50),
      );
      return;
    }
    // Open the image-type picker modal which gives the file to handleFileUpload
    setImageTypeModal(file);
  };

  // ── Clipboard paste handler ────────────────────────────────────────────────
  const handlePaste = (e) => {
    if (isLoading) return;
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
      if (item.kind === "file" && item.type.startsWith("image/")) {
        e.preventDefault();
        const file = item.getAsFile();
        if (file) handleImageFile(file);
        break;
      }
    }
  };

  // ── Drag-and-drop handlers ─────────────────────────────────────────────────
  const handleDragOver = (e) => {
    e.preventDefault();
    if (!isLoading) setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    // Only clear if we leave the drop zone entirely (not child elements)
    if (!e.currentTarget.contains(e.relatedTarget)) {
      setIsDragOver(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (isLoading) return;
    const file = e.dataTransfer.files?.[0];
    if (file) handleImageFile(file);
  };

  // ── Called when user picks a type in the modal ─────────────────────────────
  const handleModalTypeSelect = async (type) => {
    const file = imageTypeModal;
    setImageTypeModal(null);
    if (!file) return;

    // Build a synthetic event-like object so we can reuse handleFileUpload
    const fakeEvent = {
      target: { files: [file], value: null },
    };
    await handleFileUpload(fakeEvent, type);
  };

  return (
    <>
      <div className="max-w-4xl mx-auto h-[calc(100vh-120px)] flex flex-col p-4">
        {/* Header */}
        <div className="flex justify-between items-center mb-4 px-2">
          <div>
            <h1 className="text-xl font-bold text-[var(--accent-primary)] italic">
              Medical Triage Session
            </h1>
            <p className="text-xs text-[var(--text-secondary)] font-light">
              Encrypted &amp; Anonymous AI Consultation
            </p>
          </div>
          <div className="flex items-center gap-2">
            {/* Session Active badge */}
            <AnimatePresence>
              {sessionID && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[var(--bg-primary)] border border-[var(--panel-border)]"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--bg-primary)]0 animate-pulse" />
                  <span className="text-[10px] font-semibold text-[var(--accent-active)] tracking-wide">
                    Session ···{sessionID.slice(-8)}
                  </span>
                </motion.div>
              )}
            </AnimatePresence>

            {/* New Chat button */}
            <button
              onClick={() => {
                setSessionID(null);
                setMessages([
                  {
                    id: "initial-welcome",
                    role: "assistant",
                    content:
                      "Hello! I am TriGuard AI. How are you feeling today? You can describe your symptoms, upload a document, or use voice mode.",
                    html: sanitize(
                      "Hello! I am TriGuard AI. How are you feeling today? You can describe your symptoms, upload a document, or use voice mode.",
                    ),
                    type: "text",
                  },
                ]);
              }}
              className="skeuo-btn px-3 py-1 !rounded-full text-xs flex items-center gap-1 hover:bg-[var(--bg-primary)] transition-colors"
              title="Start a new chat session"
            >
              <RefreshCw size={11} />
              <span>New Chat</span>
            </button>

            <button className="skeuo-btn px-3 py-1 !rounded-full text-xs flex items-center space-x-1">
              <Globe size={14} /> <span>English</span>
            </button>
          </div>
        </div>

        {/* Chat Area — drop zone */}
        <div
          className={`flex-1 skeuo-panel overflow-y-auto mb-4 space-y-6 scrollbar-hide p-6 transition-all duration-200 relative ${
            isDragOver ? "ring-2 ring-[var(--accent-primary)] bg-[var(--bg-primary)] ring-inset" : ""
          }`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {/* Drag overlay hint */}
          {isDragOver && (
            <div className="absolute inset-0 z-10 flex flex-col items-center justify-center pointer-events-none">
              <div className="p-6 rounded-3xl bg-[var(--bg-secondary)]/90 backdrop-blur-sm border border-[var(--panel-border)] flex flex-col items-center gap-3">
                <ScanSearch size={40} className="text-[var(--accent-primary)] animate-pulse" />
                <p className="text-[var(--accent-active)] font-semibold text-lg">
                  Drop image or PDF here
                </p>
                <p className="text-[var(--text-secondary)] text-xs">
                  JPEG · PNG · WebP · GIF · BMP · TIFF · PDF
                </p>
              </div>
            </div>
          )}
          <AnimatePresence>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 20, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.4, ease: "easeOut" }}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`flex max-w-[80%] ${msg.role === "user" ? "flex-row-reverse" : "flex-row"} items-start gap-3`}
                >
                  <div
                    className={`p-2 skeuo-panel !rounded-full shrink-0 flex items-center justify-center w-10 h-10`}
                  >
                    {msg.role === "user" ? (
                      <User size={18} className="text-[var(--text-secondary)]" />
                    ) : (
                      <Bot
                        size={18}
                        className="text-[var(--accent-primary)]"
                      />
                    )}
                  </div>

                  <div
                    className={`relative px-5 py-3 ${
                      msg.role === "user"
                        ? "skeuo-btn-primary rounded-2xl rounded-tr-none !cursor-default !active:translate-y-0 text-white"
                        : "skeuo-panel rounded-2xl rounded-tl-none font-medium text-[var(--text-primary)]"
                    }`}
                  >
                    {msg.risk &&
                      msg.role === "assistant" &&
                      !msg.parsed &&
                      msg.type !== "xray" &&
                      msg.type !== "voice" && (
                        <div className="mb-2">
                          <RiskBadge level={msg.risk} />
                        </div>
                      )}

                    {/* Assistant message: use rich card if parsed, else raw HTML */}
                    {msg.role === "assistant" && msg.parsed ? (
                      <TriageResponseCard
                        parsed={msg.parsed}
                        riskLevel={msg.risk}
                        rawText={msg.content}
                        nutritionImageUrl={msg.nutritionImageUrl || null}
                      />
                    ) : msg.role === "assistant" && msg.type === "xray" ? (
                      <XrayResultCard text={msg.content} riskLevel={msg.risk} />
                    ) : (
                      <p
                        className="whitespace-pre-wrap text-sm leading-relaxed"
                        dangerouslySetInnerHTML={{
                          __html: msg.html ?? sanitize(msg.content),
                        }}
                      />
                    )}

                    {/* Only show legacy imageUrl for non-card messages (e.g. X-ray analysis) */}
                    {msg.imageUrl && !msg.parsed && (
                      <img
                        src={msg.imageUrl}
                        alt="Analysis"
                        className="mt-3 rounded-lg border border-[var(--border-color)]"
                      />
                    )}

                    {msg.audioUrl && (
                      <audio
                        controls
                        autoPlay
                        src={msg.audioUrl}
                        className="mt-3 w-full h-8 scale-90 origin-left"
                      />
                    )}
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {isLoading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex justify-start items-center space-x-2 text-[var(--accent-primary)]"
            >
              <Bot
                size={18}
                className="animate-bounce text-[var(--accent-primary)]"
              />
              <div className="flex space-x-1">
                <span className="w-1.5 h-1.5 bg-orange-400 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                <span className="w-1.5 h-1.5 bg-orange-400 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                <span className="w-1.5 h-1.5 bg-orange-400 rounded-full animate-bounce"></span>
              </div>
            </motion.div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Input Area */}
        <div className="relative">
          <div className="skeuo-panel p-3 !rounded-3xl flex items-end gap-3 0_4px_10px_rgba(0,0,0,0.1)]">
            <div
              className={`${isLoading ? "opacity-50 pointer-events-none" : ""}`}
            >
              <VoiceToggle isActive={voiceMode} onClick={openVoiceMode} />
            </div>

            <div className="flex-1 flex flex-col gap-2">
              {/* Upload buttons: 3 distinct modes */}
              <div
                className={`flex gap-2 ${isLoading ? "opacity-50 pointer-events-none" : ""}`}
              >
                {/* 1. Medical Document / Prescription → OCR */}
                <label
                  className="cursor-pointer p-2 hover:bg-[var(--bg-primary)] rounded-full transition-colors text-[var(--text-secondary)] hover:text-[var(--accent-active)] relative group"
                  title="Upload Medical Document / Prescription (OCR)"
                >
                  <input
                    type="file"
                    className="hidden"
                    disabled={isLoading}
                    onChange={(e) => handleFileUpload(e, "document")}
                    accept="image/jpeg,image/png,image/webp,image/gif,image/bmp,image/tiff,application/pdf"
                  />
                  <FileText size={20} />
                  <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 text-[10px] bg-slate-800 text-white rounded-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                    Medical Report / Prescription
                  </span>
                </label>

                {/* 2. Body / Skin Image → Vision pipeline */}
                <label
                  className="cursor-pointer p-2 hover:bg-[var(--bg-primary)] rounded-full transition-colors text-[var(--text-secondary)] hover:text-[var(--accent-active)] relative group"
                  title="Upload Body or Skin Image (Visual Analysis)"
                >
                  <input
                    type="file"
                    className="hidden"
                    disabled={isLoading}
                    onChange={(e) => handleFileUpload(e, "image")}
                    accept="image/jpeg,image/png,image/webp,image/gif,image/bmp,image/tiff"
                  />
                  <Camera size={20} />
                  <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 text-[10px] bg-slate-800 text-white rounded-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                    Body / Skin Image
                  </span>
                </label>

                {/* 3. X-Ray → Xray analysis pipeline */}
                <label
                  className="cursor-pointer p-2 hover:bg-[var(--bg-primary)] rounded-full transition-colors text-[var(--text-secondary)] hover:text-[var(--accent-active)] relative group"
                  title="Upload X-Ray for AI Radiological Analysis"
                >
                  <input
                    type="file"
                    className="hidden"
                    disabled={isLoading}
                    onChange={(e) => handleFileUpload(e, "xray")}
                    accept="image/jpeg,image/png,image/webp,image/gif,image/bmp,image/tiff"
                  />
                  <Stethoscope size={20} />
                  <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 text-[10px] bg-slate-800 text-white rounded-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                    X-Ray Analysis
                  </span>
                </label>
              </div>

              <textarea
                rows="1"
                value={input}
                disabled={isLoading}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) =>
                  e.key === "Enter" &&
                  !e.shiftKey &&
                  (e.preventDefault(), handleSend())
                }
                placeholder={
                  isLoading
                    ? "Please wait..."
                    : "Type symptoms or medical concerns..."
                }
                className="w-full skeuo-input resize-none max-h-32 py-3 disabled:opacity-50"
                onPaste={handlePaste}
              />

              {/* Emergency call consent */}
              <label className="flex items-center gap-2 cursor-pointer select-none group px-1">
                <input
                  type="checkbox"
                  checked={consentForCall}
                  onChange={(e) => setConsentForCall(e.target.checked)}
                  className="w-3.5 h-3.5 accent-red-500 cursor-pointer"
                />
                <span className="text-[10px] text-[var(--text-secondary)] group-hover:text-gray-700 transition-colors">
                  🚨 Consent to emergency call if risk is critical
                </span>
              </label>
            </div>

            <button
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              className="p-3 skeuo-btn-primary !rounded-2xl disabled:opacity-50 disabled:!cursor-not-allowed disabled:!transform-none"
            >
              {isLoading ? (
                <Loader2 className="animate-spin" />
              ) : (
                <Send size={20} />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Image Type Picker Modal */}
      <ImageTypeModal
        file={imageTypeModal}
        onSelect={handleModalTypeSelect}
        onCancel={() => setImageTypeModal(null)}
      />

      {/* Fullscreen Voice Interface — renders over everything when voiceMode=true */}
      <AnimatePresence>
        {voiceMode && (
          <VoiceInterface
            key="voice-interface"
            onClose={() => setVoiceMode(false)}
            onResult={handleVoiceResult}
            sessionId={sessionID}
            userId={
              JSON.parse(localStorage.getItem("user") || "{}")?.user_id || null
            }
            token={localStorage.getItem("token") || null}
          />
        )}
      </AnimatePresence>
    </>
  );
};

// ── Image Type Picker Modal ────────────────────────────────────────────────────
const ImageTypeModal = ({ file, onSelect, onCancel }) => {
  if (!file) return null;

  const options = [
    {
      type: "document",
      icon: <FileScan size={28} className="text-[var(--accent-primary)]" />,
      label: "Medical Document",
      sublabel: "Prescription, lab report, doctor's notes",
      glow: "orange",
    },
    {
      type: "image",
      icon: <Image size={28} className="text-amber-400" />,
      label: "Body / Skin Image",
      sublabel: "Wound, rash, skin condition",
      glow: "amber",
    },
    {
      type: "xray",
      icon: <Stethoscope size={28} className="text-rose-400" />,
      label: "X-Ray / Scan",
      sublabel: "Radiological image for AI analysis",
      glow: "rose",
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm"
        onClick={onCancel}
      />
      {/* Modal card */}
      <motion.div
        initial={{ opacity: 0, scale: 0.92, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.92 }}
        className="relative z-10 skeuo-panel p-8 max-w-sm w-full"
      >
        <button
          onClick={onCancel}
          className="absolute top-4 right-4 p-1 hover:bg-[var(--bg-primary)] rounded-full text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          <X size={18} />
        </button>

        <div className="mb-6 text-center">
          <div className="w-12 h-12 rounded-2xl bg-[var(--bg-primary)] border border-[var(--panel-border)] flex items-center justify-center mx-auto mb-3">
            <ScanSearch size={24} className="text-[var(--accent-primary)]" />
          </div>
          <h3 className="text-lg font-bold text-[var(--accent-primary)]">Select Image Type</h3>
          <p className="text-xs text-[var(--text-secondary)] mt-1 truncate max-w-[220px] mx-auto">
            {file.name || "pasted image"}
          </p>
        </div>

        <div className="flex flex-col gap-3">
          {options.map(({ type, icon, label, sublabel, glow }) => (
            <button
              key={type}
              onClick={() => onSelect(type)}
              className={`flex items-center gap-4 p-4 rounded-2xl bg-[var(--bg-secondary)] border border-[var(--panel-border)] hover:border-${glow}-300 hover:bg-${glow}-50 transition-all text-left  hover: group`}
            >
              <div
                className={`p-2 rounded-xl bg-${glow}-50 border border-${glow}-200 shrink-0`}
              >
                {icon}
              </div>
              <div>
                <p className={`font-semibold text-[var(--text-primary)] text-sm group-hover:text-${glow}-700 transition-colors`}>
                  {label}
                </p>
                <p className="text-xs text-[var(--text-secondary)] mt-0.5">{sublabel}</p>
              </div>
            </button>
          ))}
        </div>
      </motion.div>
    </div>
  );
};

export default TriageChat;
