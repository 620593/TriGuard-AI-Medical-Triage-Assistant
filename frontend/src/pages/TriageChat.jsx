import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Send,
  Upload,
  Paperclip,
  Camera,
  Globe,
  Loader2,
  Bot,
  User,
} from "lucide-react";
import { triageAPI } from "../api/client";
import RiskBadge from "../components/RiskBadge";
import VoiceToggle from "../components/VoiceToggle";

const TriageChat = () => {
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: "assistant",
      content:
        "Hello! I am TriGuard AI. How are you feeling today? You can describe your symptoms, upload a document, or use voice mode.",
      type: "text",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isVoiceActive, setIsVoiceActive] = useState(false);
  const [sessionID, setSessionID] = useState(`session_${Date.now()}`);

  const chatEndRef = useRef(null);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = {
      id: Date.now(),
      role: "user",
      content: input,
      type: "text",
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await triageAPI.triage({
        session_id: sessionID,
        message: input,
      });

      const data = response.data;
      const aiMessage = {
        id: Date.now() + 1,
        role: "assistant",
        content: data.response,
        risk: data.risk_level,
        type: "text",
      };

      setMessages((prev) => [...prev, aiMessage]);
    } catch (error) {
      console.error("Triage Error:", error);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: "assistant",
          content:
            "I encountered an error connecting to the medical server. Please try again.",
          error: true,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (event, type) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append(type === "voice" ? "audio" : "image", file);
    formData.append("session_id", sessionID);

    setMessages((prev) => [
      ...prev,
      {
        id: Date.now(),
        role: "user",
        content: `Uploaded ${type}: ${file.name}`,
        type: "file",
      },
    ]);
    setIsLoading(true);

    try {
      let response;
      if (type === "image") response = await triageAPI.image(formData);
      else if (type === "xray") response = await triageAPI.xray(formData);

      const data = response.data;
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: "assistant",
          content: data.analysis || data.response,
          risk: data.risk_level,
          imageUrl: data.nutrition_image || data.image_url,
        },
      ]);
    } catch (error) {
      console.error("Upload Error:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto h-[calc(100vh-120px)] flex flex-col p-4">
      {/* Header Info */}
      <div className="flex justify-between items-center mb-4 px-2">
        <div>
          <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100 italic">
            Medical Triage Session
          </h1>
          <p className="text-xs text-slate-500">
            Encrypted & Anonymous AI Consultation
          </p>
        </div>
        <div className="flex space-x-2">
          <button className="glass px-3 py-1 rounded-full text-xs flex items-center space-x-1 hover:bg-slate-50 transition-colors">
            <Globe size={14} /> <span>English</span>
          </button>
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 glass-card overflow-y-auto mb-4 space-y-6 scrollbar-hide">
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
                  className={`p-2 rounded-xl ${msg.role === "user" ? "bg-medical-primary/10" : "bg-white dark:bg-slate-800 shadow-sm border border-slate-100 dark:border-slate-700"}`}
                >
                  {msg.role === "user" ? (
                    <User size={18} />
                  ) : (
                    <Bot size={18} className="text-medical-primary" />
                  )}
                </div>

                <div
                  className={`relative px-5 py-3 rounded-2xl ${
                    msg.role === "user"
                      ? "bg-gradient-to-br from-medical-primary to-medical-secondary text-white rounded-tr-none"
                      : "bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 rounded-tl-none border border-slate-100 dark:border-slate-700 shadow-sm"
                  }`}
                >
                  {msg.risk && (
                    <div className="mb-2">
                      <RiskBadge level={msg.risk} />
                    </div>
                  )}
                  <p className="whitespace-pre-wrap text-sm leading-relaxed">
                    {msg.content}
                  </p>

                  {msg.imageUrl && (
                    <img
                      src={msg.imageUrl}
                      alt="Analysis"
                      className="mt-3 rounded-lg border border-slate-200"
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
            className="flex justify-start items-center space-x-2 text-slate-400"
          >
            <Bot size={18} className="animate-bounce" />
            <div className="flex space-x-1">
              <span className="w-1.5 h-1.5 bg-slate-300 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
              <span className="w-1.5 h-1.5 bg-slate-300 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
              <span className="w-1.5 h-1.5 bg-slate-300 rounded-full animate-bounce"></span>
            </div>
          </motion.div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Input Area */}
      <div className="relative">
        <div className="glass p-3 rounded-3xl flex items-end gap-3 shadow-lg border-medical-primary/10">
          <VoiceToggle
            isActive={isVoiceActive}
            onClick={() => setIsVoiceActive(!isVoiceActive)}
          />

          <div className="flex-1 flex flex-col gap-2">
            <div className="flex gap-2">
              <label className="cursor-pointer p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-full transition-colors text-slate-500">
                <input
                  type="file"
                  className="hidden"
                  onChange={(e) => handleFileUpload(e, "image")}
                  accept="image/*"
                />
                <Camera size={20} />
              </label>
              <label className="cursor-pointer p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-full transition-colors text-slate-500">
                <input
                  type="file"
                  className="hidden"
                  onChange={(e) => handleFileUpload(e, "xray")}
                  accept="image/*"
                />
                <Activity size={20} />
              </label>
            </div>

            <textarea
              rows="1"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) =>
                e.key === "Enter" &&
                !e.shiftKey &&
                (e.preventDefault(), handleSend())
              }
              placeholder="Type symptoms or medical concerns..."
              className="w-full bg-transparent border-none focus:ring-0 text-slate-800 dark:text-slate-100 resize-none max-h-32 py-2"
            />
          </div>

          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="p-3 bg-medical-primary text-white rounded-2xl hover:bg-medical-secondary transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-md"
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
  );
};

export default TriageChat;
