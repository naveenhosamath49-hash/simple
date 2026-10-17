'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Language } from '@/types/krishi';
import { translations } from '@/lib/translations';
import { Mic, MicOff, AlertCircle } from 'lucide-react';

interface VoiceSearchProps {
  language: Language;
  onTranscript: (query: string) => void;
  sunlightMode: boolean;
}

interface SpeechRecognitionEvent {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: {
      isFinal: boolean;
      [index: number]: {
        transcript: string;
      };
    };
  };
}

interface SpeechRecognitionInstance {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: (() => void) | null;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

export const VoiceSearch: React.FC<VoiceSearchProps> = ({
  language,
  onTranscript,
  sunlightMode,
}) => {
  const [isListening, setIsListening] = useState<boolean>(false);
  const [liveTranscript, setLiveTranscript] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);

  const t = translations[language];

  // Map app language to Web Speech BCP 47 language code
  const getSpeechLangCode = (lang: Language): string => {
    switch (lang) {
      case 'hi':
        return 'hi-IN';
      case 'kn':
        return 'kn-IN';
      default:
        return 'en-IN';
    }
  };

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const speechWindow = window as unknown as {
      SpeechRecognition?: new () => SpeechRecognitionInstance;
      webkitSpeechRecognition?: new () => SpeechRecognitionInstance;
    };

    const SpeechConstructor =
      speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;

    if (!SpeechConstructor) {
      setErrorMessage(t.speechNotSupported);
      return;
    }

    try {
      const recognition = new SpeechConstructor();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = getSpeechLangCode(language);

      recognition.onstart = () => {
        setIsListening(true);
        setErrorMessage(null);
        setLiveTranscript('');
      };

      recognition.onresult = (event: SpeechRecognitionEvent) => {
        let interimText = '';
        let finalText = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalText += event.results[i][0].transcript;
          } else {
            interimText += event.results[i][0].transcript;
          }
        }

        const currentText = finalText || interimText;
        setLiveTranscript(currentText);

        if (finalText.trim()) {
          onTranscript(finalText.trim());
          setIsListening(false);
        }
      };

      recognition.onerror = (event: { error: string }) => {
        console.warn('Speech recognition error:', event.error);
        if (event.error !== 'no-speech') {
          setErrorMessage(`Speech error: ${event.error}`);
        }
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
    } catch (err) {
      console.warn('Speech recognition setup error:', err);
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }
    };
  }, [language, onTranscript, t.speechNotSupported]);

  const toggleListening = () => {
    if (!recognitionRef.current) {
      alert(t.speechNotSupported);
      return;
    }

    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      setErrorMessage(null);
      setLiveTranscript('');
      recognitionRef.current.lang = getSpeechLangCode(language);
      try {
        recognitionRef.current.start();
      } catch (err) {
        console.warn('Restarting recognition:', err);
        recognitionRef.current.stop();
        setTimeout(() => {
          recognitionRef.current?.start();
        }, 150);
      }
    }
  };

  return (
    <div className="relative inline-flex items-center">
      <button
        onClick={toggleListening}
        type="button"
        title={t.voiceSearchTooltip}
        className={`relative flex items-center justify-center p-3 rounded-xl transition-all shadow-sm ${
          isListening
            ? 'bg-red-600 text-white animate-pulse ring-4 ring-red-400'
            : sunlightMode
            ? 'bg-amber-400 hover:bg-amber-300 text-black font-extrabold border-2 border-black'
            : 'bg-emerald-700 hover:bg-emerald-600 text-white border border-emerald-600'
        }`}
      >
        {isListening ? (
          <MicOff className="w-5 h-5 text-white animate-bounce" />
        ) : (
          <Mic className="w-5 h-5" />
        )}
      </button>

      {/* Listening Overlay & Audio Waveform Modal */}
      {isListening && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-white border-2 border-emerald-600 rounded-2xl max-w-md w-full p-6 text-center shadow-2xl">
            <div className="w-16 h-16 mx-auto rounded-full bg-emerald-100 flex items-center justify-center text-emerald-700 mb-4 animate-pulse">
              <Mic className="w-8 h-8 text-emerald-600 animate-bounce" />
            </div>

            <h3 className="text-xl font-black text-gray-900 mb-1">
              {t.listeningPrompt}
            </h3>
            <p className="text-sm font-semibold text-emerald-700 mb-4">
              {getSpeechLangCode(language) === 'hi-IN' ? 'भाषा: हिंदी (India)' : getSpeechLangCode(language) === 'kn-IN' ? 'ಭಾಷೆ: ಕನ್ನಡ (India)' : 'Language: English (India)'}
            </p>

            {/* Audio Wave Visualizer Simulation */}
            <div className="flex items-center justify-center gap-1.5 h-12 mb-4 bg-gray-50 rounded-xl px-4 py-2 border border-gray-200">
              <span className="w-1.5 bg-emerald-600 rounded-full animate-[ping_0.8s_ease-in-out_infinite] h-4"></span>
              <span className="w-1.5 bg-emerald-700 rounded-full animate-[ping_0.6s_ease-in-out_infinite] h-8"></span>
              <span className="w-1.5 bg-emerald-500 rounded-full animate-[ping_1.0s_ease-in-out_infinite] h-10"></span>
              <span className="w-1.5 bg-emerald-800 rounded-full animate-[ping_0.7s_ease-in-out_infinite] h-6"></span>
              <span className="w-1.5 bg-emerald-600 rounded-full animate-[ping_0.9s_ease-in-out_infinite] h-9"></span>
              <span className="w-1.5 bg-emerald-500 rounded-full animate-[ping_0.5s_ease-in-out_infinite] h-5"></span>
            </div>

            <div className="min-h-[48px] bg-emerald-50 rounded-lg p-3 text-base font-bold text-emerald-950 mb-3 border border-emerald-200">
              {liveTranscript ? `"${liveTranscript}"` : t.listeningHint}
            </div>

            <button
              onClick={() => {
                if (recognitionRef.current) recognitionRef.current.stop();
                setIsListening(false);
              }}
              type="button"
              className="w-full py-2.5 rounded-xl bg-gray-900 hover:bg-gray-800 text-white font-bold text-sm"
            >
              Cancel Listening
            </button>
          </div>
        </div>
      )}

      {errorMessage && (
        <div className="absolute top-full left-0 mt-2 z-30 p-2 bg-red-100 border border-red-300 text-red-800 text-xs rounded-lg shadow-md whitespace-nowrap flex items-center gap-1.5">
          <AlertCircle className="w-3.5 h-3.5 text-red-600" />
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  );
};
