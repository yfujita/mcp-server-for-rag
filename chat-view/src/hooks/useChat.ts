import { useState, useCallback, useRef } from 'react';
import type { Message, ChatState } from '../types';

export const useChat = (sessionId: string | null, onSessionCreated?: (id: string) => void) => {
    const [chatState, setChatState] = useState<ChatState>({
        messages: [],
        isLoading: false,
    });

    // ストリーミング処理の中断用
    const abortControllerRef = useRef<AbortController | null>(null);
    const streamingSessionIdRef = useRef<string | null>(null);

    // 履歴ロード
    const loadHistory = useCallback(async (sid: string) => {
        console.log("Loading history for session:", sid);
        if (chatState.isLoading && streamingSessionIdRef.current === sid) {
            console.log("Skipping loadHistory because it matches current streaming session.");
            return;
        }
        try {
            setChatState(prev => ({ ...prev, isLoading: true }));
            const res = await fetch(`/api/sessions/${sid}`);
            if (res.ok) {
                const data = await res.json();
                setChatState({
                    messages: data.messages || [],
                    isLoading: false
                });
            } else {
                setChatState(prev => ({ ...prev, isLoading: false }));
            }
        } catch (e) {
            console.error(e);
            setChatState(prev => ({ ...prev, isLoading: false }));
        }
    }, []);

    // メッセージ送信
    const sendMessage = useCallback(async (message: string) => {
        if (!message.trim()) return;

        // 前回の通信があれば中断
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        abortControllerRef.current = new AbortController();
        streamingSessionIdRef.current = sessionId;
        console.log("Starting sendMessage for session:", sessionId);

        const userMsg: Message = { role: 'user', content: message };

        setChatState(prev => ({
            ...prev,
            messages: [...prev.messages, userMsg],
            isLoading: true,
            statusMessage: "Connecting...",
        }));

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId, message }),
                signal: abortControllerRef.current.signal,
            });

            if (!response.body) throw new Error("No response body");

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let currentAssistantMessage = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('event: ')) {
                        const [eventLine, ...dataLines] = line.split('\n');
                        const eventType = eventLine.replace('event: ', '').trim();
                        const dataStr = dataLines.join('\n').replace('data: ', '').trim();

                        if (!dataStr) continue;

                        try {
                            const data = JSON.parse(dataStr);

                            switch (eventType) {
                                case 'session_id':
                                    if (!sessionId && onSessionCreated) {
                                        onSessionCreated(data.session_id);
                                    }
                                    break;

                                case 'status':
                                    setChatState(prev => ({
                                        ...prev,
                                        statusMessage: `Executing tool: ${data.tool}...`
                                    }));
                                    break;

                                case 'message':
                                    currentAssistantMessage += data.content;
                                    setChatState(prev => {
                                        const newMessages = [...prev.messages];
                                        const lastMsg = newMessages[newMessages.length - 1];

                                        // 最後のメッセージがAssistantかつToolCallでないなら追記
                                        if (lastMsg.role === 'assistant' && !lastMsg.tool_calls) {
                                            lastMsg.content = currentAssistantMessage;
                                        } else {
                                            // 新規メッセージとして追加
                                            newMessages.push({ role: 'assistant', content: currentAssistantMessage });
                                        }
                                        return { ...prev, messages: newMessages, statusMessage: "Generating response..." };
                                    });
                                    break;

                                // ツール実行結果やTool Call自体も履歴として扱うならここで処理可能だが、
                                // 今回はServer側で履歴保存されているため、リロード時に再現される。
                                // リアルタイム表示はstatusイベントとmessageイベントでカバーする。

                                case 'done':
                                    setChatState(prev => ({ ...prev, isLoading: false, statusMessage: undefined }));
                                    break;

                                case 'error':
                                    console.error(data.error);
                                    setChatState(prev => ({
                                        ...prev,
                                        isLoading: false,
                                        statusMessage: `Error: ${data.error}`
                                    }));
                                    break;
                            }
                        } catch (e) {
                            console.error("JSON Parse error", e);
                        }
                    }
                }
            }
        } catch (e: any) {
            if (e.name !== 'AbortError') {
                console.error(e);
                setChatState(prev => ({ ...prev, isLoading: false, statusMessage: "Network Error" }));
            }
        }
    }, [sessionId, onSessionCreated]);

    const clearChat = useCallback(() => {
        setChatState({ messages: [], isLoading: false });
    }, []);

    return { chatState, sendMessage, loadHistory, clearChat };
};