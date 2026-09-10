"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Mic, MicOff, Square } from "lucide-react";
import { useLocale } from "@/components/locale";

/**
 * Voice dictation using the browser's own speech recognition.
 *
 * Entirely client-side: no audio, transcript or permission ever reaches the
 * shift.AI backend. Unsupported browsers get a disabled control with an
 * explanation instead of a broken button.
 */

type RecognitionAlternative = { transcript: string };
type RecognitionResult = {
  isFinal: boolean;
  0: RecognitionAlternative;
  length: number;
};
type RecognitionEvent = {
  resultIndex: number;
  results: { length: number; [index: number]: RecognitionResult };
};
type RecognitionErrorEvent = { error: string };
type Recognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: RecognitionEvent) => void) | null;
  onerror: ((event: RecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
};
type RecognitionConstructor = new () => Recognition;

const constructor = (): RecognitionConstructor | undefined => {
  if (typeof window === "undefined") return undefined;
  const scope = window as unknown as {
    SpeechRecognition?: RecognitionConstructor;
    webkitSpeechRecognition?: RecognitionConstructor;
  };
  return scope.SpeechRecognition || scope.webkitSpeechRecognition;
};

const messages: Record<string, string> = {
  "not-allowed":
    "Microphone access was blocked. Allow microphone permission in your browser to use voice input.",
  "service-not-allowed":
    "Microphone access was blocked. Allow microphone permission in your browser to use voice input.",
  "audio-capture":
    "No microphone was found. Connect one and try voice input again.",
  network: "Speech recognition needs a connection. Check your network.",
  "no-speech": "No speech was detected. Try speaking a little louder.",
};

export function VoiceInputButton({
  disabled,
  onTranscript,
  onStatus,
}: {
  disabled?: boolean;
  /** Called with the text captured so far; the composer stays editable. */
  onTranscript: (text: string, final: boolean) => void;
  onStatus: (status: { listening: boolean; error?: string }) => void;
}) {
  const { language } = useLocale();
  const [supported, setSupported] = useState(true);
  const [listening, setListening] = useState(false);
  const recognition = useRef<Recognition | null>(null);
  const settled = useRef("");

  useEffect(() => setSupported(!!constructor()), []);

  const stop = useCallback(() => {
    recognition.current?.stop();
    setListening(false);
  }, []);

  useEffect(
    () => () => {
      recognition.current?.abort();
      recognition.current = null;
    },
    [],
  );

  const start = () => {
    const Ctor = constructor();
    if (!Ctor) {
      setSupported(false);
      return;
    }
    const engine = new Ctor();
    engine.lang = language === "en" ? navigator.language || "en-US" : language;
    engine.continuous = true;
    engine.interimResults = true;
    engine.maxAlternatives = 1;
    settled.current = "";
    engine.onstart = () => {
      setListening(true);
      onStatus({ listening: true });
    };
    engine.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const text = result[0]?.transcript || "";
        if (result.isFinal) settled.current += text;
        else interim += text;
      }
      onTranscript((settled.current + interim).trim(), false);
    };
    engine.onerror = (event) => {
      setListening(false);
      if (event.error === "aborted") return;
      onStatus({
        listening: false,
        error:
          messages[event.error] ||
          "Voice input stopped unexpectedly. You can keep typing.",
      });
    };
    engine.onend = () => {
      setListening(false);
      onStatus({ listening: false });
      onTranscript(settled.current.trim(), true);
    };
    recognition.current = engine;
    try {
      engine.start();
    } catch {
      setListening(false);
      onStatus({
        listening: false,
        error: "Voice input could not start. You can keep typing.",
      });
    }
  };

  if (!supported)
    return (
      <button
        type="button"
        className="dx-icon-button"
        disabled
        aria-label="Voice input is unavailable"
        title="Speech input isn’t supported in this browser."
      >
        <MicOff size={17} />
      </button>
    );

  return (
    <button
      type="button"
      className={`dx-icon-button dx-mic ${listening ? "is-listening" : ""}`}
      disabled={disabled}
      aria-label={listening ? "Stop voice input" : "Start voice input"}
      aria-pressed={listening}
      title={listening ? "Stop listening" : "Speak your answer"}
      onClick={() => (listening ? stop() : start())}
    >
      {listening ? <Square size={15} /> : <Mic size={17} />}
    </button>
  );
}
