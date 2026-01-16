import React from 'react';
import { MessageSquarePlus, MessageSquare, Loader2 } from 'lucide-react';
import type { Session } from '../types';
import { clsx } from 'clsx';

interface SidebarProps {
    sessions: Session[];
    currentSessionId: string | null;
    onSelectSession: (id: string) => void;
    onNewChat: () => void;
    isLoading: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
    sessions,
    currentSessionId,
    onSelectSession,
    onNewChat,
    isLoading
}) => {
    return (
        <div className="w-64 bg-gray-900 text-white flex flex-col h-full border-r border-gray-700">
            <div className="p-4 border-b border-gray-700">
                <button
                    onClick={onNewChat}
                    className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded transition-colors"
                >
                    <MessageSquarePlus size={20} />
                    New Chat
                </button>
            </div>

            <div className="flex-1 overflow-y-auto p-2">
                {isLoading && sessions.length === 0 ? (
                    <div className="flex justify-center p-4">
                        <Loader2 className="animate-spin text-gray-400" />
                    </div>
                ) : (
                    <div className="space-y-1">
                        {sessions.map((session) => (
                            <button
                                key={session.session_id}
                                onClick={() => onSelectSession(session.session_id)}
                                className={clsx(
                                    "w-full text-left p-3 rounded flex items-start gap-3 transition-colors text-sm",
                                    currentSessionId === session.session_id
                                        ? "bg-gray-700 text-white"
                                        : "text-gray-400 hover:bg-gray-800 hover:text-white"
                                )}
                            >
                                <MessageSquare size={16} className="mt-1 shrink-0" />
                                <div className="truncate">
                                    <div className="font-medium truncate">
                                        {session.title || "No Title"}
                                    </div>
                                    <div className="text-xs text-gray-500 mt-1">
                                        {new Date(session.updated_at).toLocaleString()}
                                    </div>
                                </div>
                            </button>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};