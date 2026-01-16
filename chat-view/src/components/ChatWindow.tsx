import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot, User, Loader2, Cpu } from 'lucide-react';
import type { ChatState, Message } from '../types';
import { clsx } from 'clsx';

interface ChatWindowProps {
    chatState: ChatState;
    onSendMessage: (message: string) => void;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({ chatState, onSendMessage }) => {
    const [input, setInput] = useState('');
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [chatState.messages, chatState.statusMessage]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || chatState.isLoading) return;
        onSendMessage(input);
        setInput('');
    };

    // メッセージレンダリングヘルパー
    const renderMessageContent = (msg: Message) => {
        if (msg.role === 'tool') {
            return (
                <div className="text-xs font-mono bg-gray-100 p-2 rounded mt-1 text-gray-600 overflow-x-auto">
                    <div className="font-bold mb-1 flex items-center gap-1">
                        <Cpu size={12} /> Tool Result: {msg.name}
                    </div>
                    <pre>{msg.content}</pre>
                </div>
            );
        }

        // Tool Calls (AIがツールを呼び出した記録)
        if (msg.tool_calls && msg.tool_calls.length > 0) {
            return (
                <div className="space-y-2">
                    {msg.content && <div className="whitespace-pre-wrap">{msg.content}</div>}
                    {msg.tool_calls.map((tc, idx) => (
                        <div key={idx} className="text-xs bg-blue-50 text-blue-800 p-2 rounded border border-blue-100 font-mono">
                            <div className="font-semibold">🛠 Call: {tc.function.name}</div>
                            <div className="truncate opacity-75">{tc.function.arguments}</div>
                        </div>
                    ))}
                </div>
            );
        }

        return <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>;
    };

    return (
        <div className="flex-1 flex flex-col h-full bg-white relative">
            {/* メッセージリスト */}
            <div className="flex-1 overflow-y-auto p-4 space-y-6">
                {chatState.messages.length === 0 && (
                    <div className="h-full flex items-center justify-center text-gray-400">
                        <p>何でも聞いてください。</p>
                    </div>
                )}

                {chatState.messages.filter(msg => msg.role !== 'system').map((msg, index) => (
                    <div
                        key={index}
                        className={clsx(
                            "flex gap-4 max-w-3xl mx-auto",
                            msg.role === 'user' ? "flex-row-reverse" : "flex-row"
                        )}
                    >
                        <div
                            className={clsx(
                                "w-8 h-8 rounded-full flex items-center justify-center shrink-0",
                                msg.role === 'user' ? "bg-gray-800 text-white" :
                                    msg.role === 'tool' ? "bg-gray-200 text-gray-600" : "bg-blue-600 text-white"
                            )}
                        >
                            {msg.role === 'user' ? <User size={18} /> : msg.role === 'tool' ? <Cpu size={18} /> : <Bot size={18} />}
                        </div>

                        <div className={clsx(
                            "rounded-lg p-4 shadow-sm max-w-[80%]",
                            msg.role === 'user' ? "bg-gray-800 text-white" : "bg-gray-50 border border-gray-100 text-gray-800"
                        )}>
                            {renderMessageContent(msg)}
                        </div>
                    </div>
                ))}

                {/* ステータス表示（ツール実行中など） */}
                {chatState.isLoading && chatState.statusMessage && (
                    <div className="flex items-center justify-center gap-2 text-sm text-gray-500 py-2 animate-pulse">
                        <Loader2 size={16} className="animate-spin" />
                        {chatState.statusMessage}
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* 入力フォーム */}
            <div className="border-t border-gray-200 p-4 bg-white">
                <form onSubmit={handleSubmit} className="max-w-3xl mx-auto flex gap-2">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="メッセージを入力..."
                        disabled={chatState.isLoading}
                        className="flex-1 p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                    />
                    <button
                        type="submit"
                        disabled={!input.trim() || chatState.isLoading}
                        className="bg-blue-600 text-white p-3 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                        <Send size={20} />
                    </button>
                </form>
            </div>
        </div>
    );
};