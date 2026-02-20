/**
 * Agent Chat Page
 * Interactive chat with AI agents featuring streaming responses
 * and reasoning/tool-call visualization
 */
'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useAgents, useConversations, useConversation } from '@/lib/hooks/use-api';
import { Agent, Conversation, Message, ToolCall } from '@/lib/api-client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { 
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { 
  Bot, 
  Send, 
  Plus, 
  MessageSquare, 
  Brain,
  Wrench,
  ChevronRight,
  Loader2,
  Clock
} from 'lucide-react';
import { cn } from '@/lib/utils';

// Message types for streaming
interface StreamingChunk {
  type: 'content' | 'thought' | 'tool_call' | 'tool_result' | 'done';
  content: string;
  toolCall?: ToolCall;
}

// Reasoning Card Component
function ReasoningCard({ 
  thought,
  toolCalls,
  isActive 
}: { 
  thought?: string; 
  toolCalls?: ToolCall[];
  isActive?: boolean;
}) {
  if (!thought && (!toolCalls || toolCalls.length === 0)) return null;

  return (
    <div className="ml-12 mt-2 mb-4 space-y-2">
      {thought && (
        <Card className={cn(
          "border-l-4 border-l-purple-500 bg-purple-50/50 dark:bg-purple-950/10",
          isActive && "animate-pulse"
        )}>
          <CardContent className="p-3">
            <div className="flex items-center gap-2 text-purple-700 dark:text-purple-300 mb-2">
              <Brain className="h-4 w-4" />
              <span className="text-xs font-medium uppercase tracking-wide">Thinking</span>
            </div>
            <p className="text-sm text-purple-900 dark:text-purple-100">{thought}</p>
          </CardContent>
        </Card>
      )}
      
      {toolCalls?.map((toolCall, idx) => (
        <Card 
          key={toolCall.id || idx} 
          className="border-l-4 border-l-blue-500 bg-blue-50/50 dark:bg-blue-950/10"
        >
          <CardContent className="p-3">
            <div className="flex items-center gap-2 text-blue-700 dark:text-blue-300 mb-2">
              <Wrench className="h-4 w-4" />
              <span className="text-xs font-medium uppercase tracking-wide">Tool Call</span>
              <Badge variant="secondary" className="text-xs">
                {toolCall.name}
              </Badge>
            </div>
            <pre className="text-xs bg-blue-100/50 dark:bg-blue-900/20 p-2 rounded overflow-auto">
              {JSON.stringify(toolCall.arguments, null, 2)}
            </pre>
            {toolCall.result && (
              <div className="mt-2">
                <span className="text-xs text-blue-600 dark:text-blue-400">Result:</span>
                <pre className="text-xs bg-blue-100/50 dark:bg-blue-900/20 p-2 rounded mt-1 overflow-auto">
                  {JSON.stringify(toolCall.result, null, 2)}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// Chat Message Component
function ChatMessage({ 
  message, 
  streamingThought,
  streamingToolCalls,
  isStreaming 
}: { 
  message: Message;
  streamingThought?: string;
  streamingToolCalls?: ToolCall[];
  isStreaming?: boolean;
}) {
  const isUser = message.role === 'user';
  
  return (
    <div className={cn(
      "flex gap-4 py-4",
      isUser ? "flex-row" : "flex-row"
    )}>
      <Avatar className={cn(
        "h-8 w-8 shrink-0",
        isUser ? "bg-primary" : "bg-purple-600"
      )}>
        <AvatarFallback className="text-xs">
          {isUser ? 'U' : <Bot className="h-4 w-4" />}
        </AvatarFallback>
      </Avatar>
      
      <div className="flex-1 space-y-2">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm">
            {isUser ? 'You' : 'Assistant'}
          </span>
          <span className="text-xs text-muted-foreground">
            {new Date(message.created_at).toLocaleTimeString()}
          </span>
        </div>
        
        <div className="text-sm leading-relaxed whitespace-pre-wrap">
          {message.content}
          {isStreaming && !message.content && (
            <span className="inline-flex items-center">
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              Thinking...
            </span>
          )}
        </div>
        
        {!isUser && (
          <ReasoningCard
            thought={streamingThought}
            toolCalls={streamingToolCalls}
            isActive={isStreaming}
          />
        )}
      </div>
    </div>
  );
}

// Conversation Sidebar Component
function ConversationSidebar({
  agentId,
  selectedConversationId,
  onSelectConversation,
  onNewConversation,
}: {
  agentId: string;
  selectedConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
}) {
  const { data: conversations, loading } = useConversations(agentId);

  return (
    <div className="flex flex-col h-full border-r w-64 bg-muted/30">
      <div className="p-4 border-b">
        <Button 
          variant="outline" 
          className="w-full justify-start"
          onClick={onNewConversation}
        >
          <Plus className="h-4 w-4 mr-2" />
          New Chat
        </Button>
      </div>
      
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {loading ? (
            <div className="p-4 space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-10 animate-pulse rounded bg-muted" />
              ))}
            </div>
          ) : conversations?.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              No conversations yet
            </div>
          ) : (
            conversations?.map((conv) => (
              <button
                key={conv.id}
                onClick={() => onSelectConversation(conv.id)}
                className={cn(
                  "w-full text-left p-3 rounded-lg transition-colors",
                  selectedConversationId === conv.id
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-muted"
                )}
              >
                <div className="flex items-center gap-2">
                  <MessageSquare className="h-4 w-4 shrink-0" />
                  <span className="text-sm font-medium truncate">
                    {conv.title || 'Untitled Chat'}
                  </span>
                </div>
                <div className="flex items-center gap-1 mt-1 text-xs opacity-70">
                  <Clock className="h-3 w-3" />
                  {new Date(conv.updated_at).toLocaleDateString()}
                </div>
              </button>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

export default function ChatPage() {
  const { data: agents, loading: agentsLoading } = useAgents();
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const [inputMessage, setInputMessage] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingThought, setStreamingThought] = useState<string>();
  const [streamingToolCalls, setStreamingToolCalls] = useState<ToolCall[]>();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  const { data: conversation } = useConversation(
    selectedAgentId,
    selectedConversationId
  );

  // Auto-select first agent
  useEffect(() => {
    if (agents && agents.length > 0 && !selectedAgentId) {
      setSelectedAgentId(agents[0].id);
    }
  }, [agents, selectedAgentId]);

  // Update messages when conversation changes
  useEffect(() => {
    if (conversation?.messages) {
      setMessages(conversation.messages);
    }
  }, [conversation]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming]);

  const handleSendMessage = useCallback(async () => {
    if (!inputMessage.trim() || !selectedAgentId || !selectedConversationId) return;

    const userMessage: Message = {
      id: 'temp-' + Date.now(),
      conversation_id: selectedConversationId,
      role: 'user',
      content: inputMessage,
      created_at: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsStreaming(true);
    setStreamingThought(undefined);
    setStreamingToolCalls(undefined);

    // Simulate streaming response with reasoning
    // In production, this would be a real SSE connection
    setTimeout(() => {
      setStreamingThought('Let me analyze this request and determine what tools might be needed...');
    }, 500);

    setTimeout(() => {
      setStreamingToolCalls([{
        id: 'tool-1',
        name: 'search_objects',
        arguments: { query: inputMessage, limit: 5 },
      }]);
    }, 1500);

    setTimeout(() => {
      const assistantMessage: Message = {
        id: 'resp-' + Date.now(),
        conversation_id: selectedConversationId,
        role: 'assistant',
        content: `I've processed your request: "${inputMessage}". Based on my analysis, I've searched through the available objects and can provide you with relevant information.`,
        tool_calls: [{
          id: 'tool-1',
          name: 'search_objects',
          arguments: { query: inputMessage, limit: 5 },
          result: { count: 3, objects: [] },
        }],
        created_at: new Date().toISOString(),
      };
      
      setMessages(prev => [...prev, assistantMessage]);
      setIsStreaming(false);
      setStreamingThought(undefined);
      setStreamingToolCalls(undefined);
    }, 2500);
  }, [inputMessage, selectedAgentId, selectedConversationId]);

  const handleNewConversation = useCallback(() => {
    // In production, this would call the API to create a new conversation
    const newId = 'new-' + Date.now();
    setSelectedConversationId(newId);
    setMessages([]);
  }, []);

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      {/* Agent Selector & Conversation List */}
      <div className="flex flex-col w-64 border-r">
        <div className="p-4 border-b">
          <label className="text-sm font-medium mb-2 block">Select Agent</label>
          <Select
            value={selectedAgentId || ''}
            onValueChange={setSelectedAgentId}
            disabled={agentsLoading}
          >
            <SelectTrigger>
              <SelectValue placeholder="Choose an agent..." />
            </SelectTrigger>
            <SelectContent>
              {agents?.map((agent) => (
                <SelectItem key={agent.id} value={agent.id}>
                  {agent.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        
        {selectedAgentId && (
          <ConversationSidebar
            agentId={selectedAgentId}
            selectedConversationId={selectedConversationId}
            onSelectConversation={setSelectedConversationId}
            onNewConversation={handleNewConversation}
          />
        )}
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col">
        {selectedConversationId ? (
          <>
            {/* Messages */}
            <ScrollArea className="flex-1 p-4">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center">
                  <Bot className="h-12 w-12 text-muted-foreground mb-4" />
                  <h3 className="text-lg font-semibold">Start a conversation</h3>
                  <p className="text-muted-foreground mt-1">
                    Send a message to begin chatting with the agent
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {messages.map((message, idx) => (
                    <ChatMessage
                      key={message.id}
                      message={message}
                      isStreaming={isStreaming && idx === messages.length - 1 && message.role === 'assistant'}
                      streamingThought={streamingThought}
                      streamingToolCalls={streamingToolCalls}
                    />
                  ))}
                  {isStreaming && (
                    <ChatMessage
                      message={{
                        id: 'streaming',
                        conversation_id: selectedConversationId,
                        role: 'assistant',
                        content: '',
                        created_at: new Date().toISOString(),
                      }}
                      isStreaming={true}
                      streamingThought={streamingThought}
                      streamingToolCalls={streamingToolCalls}
                    />
                  )}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </ScrollArea>

            {/* Input Area */}
            <div className="border-t p-4 bg-background">
              <div className="flex gap-2 max-w-4xl mx-auto">
                <Input
                  placeholder="Type your message..."
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  disabled={isStreaming}
                  className="flex-1"
                />
                <Button 
                  onClick={handleSendMessage}
                  disabled={!inputMessage.trim() || isStreaming}
                >
                  {isStreaming ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </Button>
              </div>
              <p className="text-xs text-center text-muted-foreground mt-2">
                Agent responses may include reasoning and tool calls for transparency
              </p>
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
            <MessageSquare className="h-16 w-16 text-muted-foreground mb-4" />
            <h2 className="text-xl font-semibold">Select a conversation</h2>
            <p className="text-muted-foreground mt-2 max-w-md">
              Choose an existing conversation from the sidebar or start a new one to begin chatting
            </p>
            <Button 
              className="mt-4"
              onClick={handleNewConversation}
              disabled={!selectedAgentId}
            >
              <Plus className="h-4 w-4 mr-2" />
              New Conversation
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
