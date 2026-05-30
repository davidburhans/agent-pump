import React, { useEffect, useState, useRef } from 'react';
import { X, Send, User, Bot, Loader2 } from 'lucide-react';
import { cn } from '../utils/cn';

interface ChatModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectPath: string;
  projectName: string;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export const ChatModal: React.FC<ChatModalProps> = ({
  isOpen,
  onClose,
  projectPath,
  projectName
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setMessages([]);
      setError(null);
      setIsTyping(false);

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      // In dev mode with Vite proxy, use relative URL or target backend directly
      // Vite proxy is usually configured for /api and /ws
      let wsUrl = `${protocol}//${host}/ws/projects/${encodeURIComponent(projectPath)}/chat`;
      
      // If we're on dev server (usually 5173), we might need to route through proxy
      // The vite config likely proxies /ws, but just in case, we can use env var if it exists.
      
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('Chat WS connected');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'start') {
            setIsTyping(true);
            setMessages(prev => [...prev, { role: 'assistant', content: '' }]);
          } else if (data.type === 'chunk') {
            setMessages(prev => {
              const newMessages = [...prev];
              const lastMsg = newMessages[newMessages.length - 1];
              if (lastMsg && lastMsg.role === 'assistant') {
                lastMsg.content += data.text;
              }
              return newMessages;
            });
          } else if (data.type === 'end') {
            setIsTyping(false);
          } else if (data.type === 'error') {
            setError(data.message);
            setIsTyping(false);
          }
        } catch (e) {
          console.error('Failed to parse WS message:', e);
        }
      };

      ws.onerror = () => {
        setError('WebSocket connection error.');
        setIsTyping(false);
      };

      ws.onclose = () => {
        console.log('Chat WS disconnected');
      };

      return () => {
        ws.close();
      };
    } else {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    }
  }, [isOpen, projectPath]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const handleSend = () => {
    if (!input.trim() || isTyping || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    const query = input.trim();
    setMessages(prev => [...prev, { role: 'user', content: query }]);
    setInput('');
    setError(null);

    const history = messages.map(m => ({ role: m.role, content: m.content }));

    wsRef.current.send(JSON.stringify({
      query,
      history
    }));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div 
        className="w-full max-w-3xl h-[80vh] flex flex-col rounded-xl border shadow-2xl overflow-hidden"
        style={{ 
          background: 'var(--bg-primary)',
          borderColor: 'var(--border-subtle)'
        }}
      >
        <div 
          className="flex items-center justify-between px-6 py-4 border-b"
          style={{ 
            background: 'var(--bg-tertiary)',
            borderColor: 'var(--border-subtle)'
          }}
        >
          <div>
            <h2 className="text-xl font-display font-semibold" style={{ color: 'var(--text-primary)' }}>
              Project Chat
            </h2>
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              {projectName}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg transition-colors"
            style={{ color: 'var(--text-muted)' }}
            onMouseEnter={e => {
              e.currentTarget.style.background = 'var(--bg-hover)';
              e.currentTarget.style.color = 'var(--text-primary)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.color = 'var(--text-muted)';
            }}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 && !error && (
            <div className="h-full flex flex-col items-center justify-center text-center space-y-4 opacity-50">
              <Bot className="w-12 h-12" style={{ color: 'var(--accent-primary)' }} />
              <div>
                <p className="text-lg font-medium" style={{ color: 'var(--text-primary)' }}>How can I help with {projectName}?</p>
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Ask questions about the codebase or workflow.</p>
              </div>
            </div>
          )}
          
          {messages.map((msg, idx) => (
            <div key={idx} className={cn("flex gap-4", msg.role === 'user' ? "flex-row-reverse" : "")}>
              <div 
                className={cn(
                  "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
                  msg.role === 'user' ? "bg-blue-600" : "bg-emerald-600"
                )}
              >
                {msg.role === 'user' ? <User className="w-5 h-5 text-white" /> : <Bot className="w-5 h-5 text-white" />}
              </div>
              <div 
                className={cn(
                  "px-4 py-3 rounded-lg max-w-[80%] whitespace-pre-wrap font-mono text-sm leading-relaxed",
                  msg.role === 'user' 
                    ? "rounded-tr-none text-white bg-blue-600" 
                    : "rounded-tl-none border shadow-sm"
                )}
                style={msg.role === 'assistant' ? {
                  background: 'var(--bg-elevated)',
                  borderColor: 'var(--border-subtle)',
                  color: 'var(--text-secondary)'
                } : undefined}
              >
                {msg.content}
              </div>
            </div>
          ))}

          {error && (
            <div className="p-4 rounded-lg bg-red-900/20 border border-red-500/30 text-red-400 text-center">
              {error}
            </div>
          )}

          {isTyping && (
            <div className="flex items-center gap-2 text-sm text-gray-400 ml-12">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Assistant is typing...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <div 
          className="p-4 border-t"
          style={{ 
            background: 'var(--bg-tertiary)',
            borderColor: 'var(--border-subtle)'
          }}
        >
          <div className="flex items-end gap-3 relative">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message... (Shift+Enter for newline)"
              className="flex-1 w-full bg-transparent resize-none overflow-hidden outline-none min-h-[44px] max-h-32 px-4 py-3 rounded-lg border font-mono text-sm"
              style={{ 
                background: 'var(--bg-primary)',
                borderColor: 'var(--border-subtle)',
                color: 'var(--text-primary)'
              }}
              rows={1}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isTyping}
              className="p-3 rounded-lg flex items-center justify-center transition-colors mb-0.5 disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                background: 'var(--accent-primary)',
                color: 'white'
              }}
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};