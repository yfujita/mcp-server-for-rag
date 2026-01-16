export interface ToolCall {
    id: string;
    function: {
        name: string;
        arguments: string;
    };
}

export interface Message {
    role: 'user' | 'assistant' | 'tool' | 'system';
    content?: string;
    // ツール呼び出し情報 (assistant role)
    tool_calls?: ToolCall[];
    // ツール実行結果情報 (tool role)
    tool_call_id?: string;
    name?: string;
}

export interface Session {
    session_id: string;
    title: string | null;
    updated_at: string;
}

export interface ChatState {
    messages: Message[];
    isLoading: boolean;
    statusMessage?: string;
  }