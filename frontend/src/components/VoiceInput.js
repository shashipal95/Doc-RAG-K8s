"use client";
import { useState, useRef, useEffect } from "react";
import { Mic, MicOff } from "lucide-react";

export function VoiceInput({
    onTranscript,
    onSpeechEnd,
    onError,
    autoSend = false,
    showLanguage = false,
    th = null
}) {
    const [isListening, setIsListening] = useState(false);
    const [supportsWebSpeech, setSupportsWebSpeech] = useState(false);
// ... (rest of state logic stays same)

    const recognitionRef = useRef(null);
    const mediaRecorderRef = useRef(null);
    const chunksRef = useRef([]);
    const silenceTimerRef = useRef(null);

    // 🔥 FIX: Keep track of the absolute latest props so the mic never uses stale data
    const propsRef = useRef({ onTranscript, onSpeechEnd, onError, autoSend });
    useEffect(() => {
        propsRef.current = { onTranscript, onSpeechEnd, onError, autoSend };
    });

    useEffect(() => {
        if (typeof window !== "undefined") {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            setSupportsWebSpeech(!!SpeechRecognition);
            if (SpeechRecognition) {
                setupWebSpeechAPI();
            }
        }
    }, []);

    const setupWebSpeechAPI = () => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();

        recognition.continuous = true; // ✅ Allows natural pauses
        recognition.interimResults = true;
        recognition.maxAlternatives = 1;
        recognition.lang = navigator.language || "en-US";

        recognition.onstart = () => {
            console.log("Voice recognition started");
            setIsListening(true);
            if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
        };

        recognition.onresult = (event) => {
            let interimTranscript = "";
            let finalTranscript = "";

            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcriptText = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += transcriptText + " ";
                } else {
                    interimTranscript += transcriptText;
                }
            }

            if (finalTranscript) {
                const lang = detectLanguage(finalTranscript);
                // Use propsRef to avoid stale closures
                if (propsRef.current.onTranscript) {
                    propsRef.current.onTranscript(finalTranscript.trim(), lang);
                }
            }

            // ✅ Silence Detection Timer
            if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
            silenceTimerRef.current = setTimeout(() => {
                if (recognitionRef.current) {
                    recognitionRef.current.stop();
                }
            }, 2000); // 2-second pause triggers submission
        };

        recognition.onerror = (event) => {
            console.error("Speech recognition error:", event.error);
            setIsListening(false);

            const errCallback = propsRef.current.onError;
            if (event.error === 'not-allowed') {
                errCallback?.("Microphone access denied. Please allow microphone access.");
            } else if (event.error === 'no-speech') {
                errCallback?.("No speech detected. Please try again.");
            } else {
                errCallback?.(event.error);
            }
        };

        recognition.onend = () => {
            setIsListening(false);
            if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);

            setTimeout(() => {
                if (propsRef.current.onSpeechEnd) {
                    propsRef.current.onSpeechEnd();
                }
            }, 100);
        };

        recognitionRef.current = recognition;
    };

    const detectLanguage = (text) => {
        const devanagariRegex = /[\u0900-\u097F]/;
        if (devanagariRegex.test(text)) return "hi";
        const hindiRomanWords = /\b(kya|hai|hoon|hain|ka|ki|ke|main|aap|tum|yeh|woh|kaise|kahan|kab|kyun)\b/i;
        if (hindiRomanWords.test(text)) return "hi";
        return "en";
    };

    const startMediaRecorder = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream);

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) chunksRef.current.push(event.data);
            };

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(chunksRef.current, { type: "audio/webm" });
                chunksRef.current = [];

                try {
                    const result = await transcribeAudioBackend(audioBlob);
                    const lang = detectLanguage(result.transcript);

                    if (propsRef.current.onTranscript) {
                        propsRef.current.onTranscript(result.transcript, lang);
                    }

                    if (propsRef.current.autoSend) {
                        setTimeout(() => {
                            const event = new CustomEvent('voice-auto-send', {
                                detail: { text: result.transcript, language: lang }
                            });
                            window.dispatchEvent(event);
                        }, 300);
                    }

                    if (propsRef.current.onSpeechEnd) {
                        propsRef.current.onSpeechEnd();
                    }

                } catch (error) {
                    console.error("Transcription error:", error);
                    propsRef.current.onError?.("Failed to transcribe audio. Please try again.");
                }

                stream.getTracks().forEach(track => track.stop());
                setIsListening(false);
            };

            mediaRecorder.start();
            mediaRecorderRef.current = mediaRecorder;
            setIsListening(true);

        } catch (error) {
            console.error("Microphone error:", error);
            propsRef.current.onError?.("Could not access microphone. Please check permissions.");
            setIsListening(false);
        }
    };

    const transcribeAudioBackend = async (audioBlob) => {
        const formData = new FormData();
        formData.append("audio", audioBlob, "recording.webm");

        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/transcribe`, {
            method: "POST",
            body: formData,
            headers: {
                "Authorization": `Bearer ${localStorage.getItem("token")}`,
            },
        });

        if (!response.ok) throw new Error("Transcription failed");
        return await response.json();
    };

    const startListening = () => {
        if (supportsWebSpeech && recognitionRef.current) {
            try {
                recognitionRef.current.start();
            } catch (error) {
                console.error("Failed to start recognition:", error);
                startMediaRecorder();
            }
        } else {
            startMediaRecorder();
        }
    };

    const stopListening = () => {
        if (recognitionRef.current && supportsWebSpeech) {
            recognitionRef.current.stop();
        }
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
            mediaRecorderRef.current.stop();
        }
        setIsListening(false);
    };

    const toggleListening = () => {
        if (isListening) stopListening();
        else startListening();
    };

    return (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button
                onClick={toggleListening}
                type="button"
                className={`voice-btn ${isListening ? 'listening' : ''}`}
                style={{
                    width: 44,
                    height: 44,
                    borderRadius: "50%",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
                    position: "relative",
                    padding: 2, // Space for border
                    border: "none",
                    background: "var(--g-accent)", // The theme gradient border
                    boxShadow: isListening ? "0 0 20px var(--c-accent-glow)" : "none",
                }}
                title={isListening ? "Stop listening" : "Start voice input"}
            >
                {/* Inner Circle to create the "border" effect and provide dark background */}
                <div style={{
                    width: "100%",
                    height: "100%",
                    borderRadius: "50%",
                    background: th?.surface || (th?.isDark ? "#121212" : "#fff"), // Theme-aware background
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                }}>
                    {isListening ? (
                        <MicOff size={20} color={th?.text || "#fff"} />
                    ) : (
                        <Mic size={20} color={th?.text || (th?.isDark ? "#fff" : "#121212")} />
                    )}
                </div>
            </button>
 
            <style jsx>{`
        @keyframes pulse {
          0%, 100% { box-shadow: 0 0 0 0 var(--c-accent-glow); transform: scale(1); }
          50% { box-shadow: 0 0 0 10px rgba(0, 0, 0, 0); transform: scale(1.05); }
        }
        .voice-btn.listening {
          animation: pulse 1.5s infinite;
        }
        .voice-btn:hover {
          transform: translateY(-2px);
          filter: brightness(1.1);
        }
        .voice-btn:active {
          transform: translateY(0px) scale(0.95);
        }
      `}</style>
        </div>
    );
}

export function CompactVoiceInput({ onTranscript, onSpeechEnd, autoSend = false, th = null }) {
    return (
        <VoiceInput
            onTranscript={onTranscript}
            onSpeechEnd={onSpeechEnd}
            autoSend={autoSend}
            showLanguage={false}
            onError={(err) => console.error(err)}
            th={th}
        />
    );
}

export default VoiceInput;